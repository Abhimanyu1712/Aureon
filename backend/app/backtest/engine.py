from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.analytics.normalization import get_contract_spec
from app.backtest.benchmark import calculate_benchmark
from app.backtest.config import BacktestConfig
from app.backtest.costs import estimated_execution_cost
from app.backtest.execution import (
    BacktestSignal,
    MarketBar,
    build_trade_legs,
    load_backtest_inputs,
)
from app.backtest.metrics import calculate_metrics
from app.backtest.models import BacktestResult, EntryRejection, EquityPoint, Trade
from app.backtest.report import build_report, json_safe, write_report


@dataclass
class _PendingEntry:
    signal: BacktestSignal
    peer_contract_ids: tuple[str, ...]


@dataclass
class _OpenPosition:
    trade: Trade
    last_prices: dict[str, tuple[Decimal, date]]
    last_joint_prices: dict[str, tuple[Decimal, date]]
    entry_day_index: int
    previous_mark_to_market: Decimal = Decimal(0)
    pending_exit_reason: str | None = None
    pending_exit_z_score: Decimal | None = None


def _day_bars(
    bars: dict[tuple[str, date, str], MarketBar],
    trading_date: date,
    source_type: str,
) -> dict[str, MarketBar]:
    return {
        bar.contract_id: bar
        for (_, bar_date, bar_source), bar in bars.items()
        if bar_date == trading_date and bar_source == source_type
    }


def _is_liquid(bar: MarketBar, config: BacktestConfig) -> bool:
    return (
        bar.volume is not None
        and bar.open_interest is not None
        and bar.volume >= config.minimum_volume
        and bar.open_interest >= config.minimum_open_interest
    )


def _peer_contracts_at_signal(
    signal: BacktestSignal,
    day_bars: dict[str, MarketBar],
) -> tuple[str, ...]:
    peer_bars = [
        bar
        for bar in day_bars.values()
        if bar.symbol != signal.symbol
        and bar.expiry_date.year == signal.expiry_date.year
        and bar.expiry_date.month == signal.expiry_date.month
    ]
    peer_symbols = {bar.symbol for bar in peer_bars}
    if len(peer_symbols) < signal.peer_count or not peer_symbols:
        return ()
    return tuple(sorted(bar.contract_id for bar in peer_bars))


def _mark_position(position: _OpenPosition, day_bars: dict[str, MarketBar], trading_date: date) -> Decimal:
    mark = Decimal(0)
    for leg in position.trade.legs:
        bar = day_bars.get(leg.contract_id)
        if bar is not None and trading_date <= leg.expiry_date:
            position.last_prices[leg.contract_id] = (bar.normalized_price, trading_date)
        current = position.last_prices.get(leg.contract_id)
        if current is None:
            continue
        price = current[0]
        side = Decimal(1) if leg.position_side == "LONG" else Decimal(-1)
        mark += side * leg.contract_equivalents * leg.contract_size_grams * (
            price - leg.entry_price_per_gram
        )
    return mark


def _current_bars_for_legs(
    position: _OpenPosition,
    day_bars: dict[str, MarketBar],
) -> dict[str, MarketBar] | None:
    if any(leg.contract_id not in day_bars for leg in position.trade.legs):
        return None
    return {leg.contract_id: day_bars[leg.contract_id] for leg in position.trade.legs}


def _close_position(
    position: _OpenPosition,
    current_bars: dict[str, MarketBar],
    trading_date: date,
    days_held: int,
    config: BacktestConfig,
    exit_reason: str,
    exit_z_score: Decimal | None,
) -> Decimal:
    trade = position.trade
    target_gross = Decimal(0)
    peer_gross = Decimal(0)
    peer_entry_notional = Decimal(0)
    peer_exit_notional = Decimal(0)
    peer_entry_grams = Decimal(0)
    exit_cost = Decimal(0)

    for leg in trade.legs:
        available = current_bars.get(leg.contract_id)
        last_price, last_date = position.last_prices[leg.contract_id]
        usable_bar = available if available is not None and trading_date <= leg.expiry_date else None
        exit_price = usable_bar.normalized_price if usable_bar is not None else last_price
        price_date = usable_bar.trade_date if usable_bar is not None else last_date
        leg.exit_price_per_gram = exit_price
        leg.exit_price_date = price_date
        leg.exit_notional = leg.contract_equivalents * leg.contract_size_grams * exit_price
        direction = Decimal(1) if leg.position_side == "LONG" else Decimal(-1)
        leg.gross_pnl = direction * leg.contract_equivalents * leg.contract_size_grams * (
            exit_price - leg.entry_price_per_gram
        )
        leg.exit_cost = estimated_execution_cost(leg.exit_notional, config)
        exit_cost += leg.exit_cost
        if leg.contract_id == trade.target_contract_id:
            target_gross += leg.gross_pnl
        else:
            peer_gross += leg.gross_pnl
            peer_entry_notional += leg.entry_notional
            peer_exit_notional += leg.exit_notional
            peer_entry_grams += leg.contract_equivalents * leg.contract_size_grams

    trade.target_exit_price = next(
        leg.exit_price_per_gram for leg in trade.legs if leg.contract_id == trade.target_contract_id
    )
    trade.peer_entry_value = peer_entry_notional / peer_entry_grams if peer_entry_grams else Decimal(0)
    trade.peer_exit_value = peer_exit_notional / peer_entry_grams if peer_entry_grams else Decimal(0)
    trade.target_leg_gross_pnl = target_gross
    trade.peer_leg_gross_pnl = peer_gross
    trade.gross_pnl = target_gross + peer_gross
    trade.transaction_cost += exit_cost
    trade.net_pnl = trade.gross_pnl - trade.transaction_cost
    trade.return_on_capital = trade.net_pnl / config.initial_capital
    trade.exit_date = min(trading_date, *(leg.expiry_date for leg in trade.legs))
    trade.exit_z_score = exit_z_score
    trade.days_held = days_held
    trade.exit_reason = exit_reason
    trade.status = "COMPLETED"
    return exit_cost


class BacktestEngine:
    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig.from_environment()

    def run(
        self,
        bars: dict[tuple[str, date, str], MarketBar],
        signals: dict[tuple[str, date, str], BacktestSignal],
        *,
        dataset_type: str = "DEMO",
        source_files: tuple[str, ...] = (),
    ) -> BacktestResult:
        if not bars or not signals:
            raise ValueError("Backtest requires Stage 3 bars and Stage 4 signals.")
        source_types = {bar.source_type for bar in bars.values()}
        if len(source_types) != 1:
            raise ValueError("Backtest inputs must contain exactly one source type.")
        source_type = next(iter(source_types))
        dates = sorted({bar.trade_date for bar in bars.values()})
        date_indexes = {trading_date: index for index, trading_date in enumerate(dates)}
        contract_expiries = {bar.contract_id: bar.expiry_date for bar in bars.values()}
        signals_by_date: dict[date, list[BacktestSignal]] = {}
        for signal in signals.values():
            signals_by_date.setdefault(signal.trade_date, []).append(signal)

        trades: list[Trade] = []
        rejections: list[EntryRejection] = []
        equity: list[EquityPoint] = []
        pending_entry: _PendingEntry | None = None
        position: _OpenPosition | None = None
        capital = self.config.initial_capital

        for trading_date in dates:
            today = _day_bars(bars, trading_date, source_type)
            starting_equity = capital
            daily_pnl = Decimal(0)
            daily_cost = Decimal(0)

            if position is not None:
                trade = position.trade
                earliest_expiry = min(leg.expiry_date for leg in trade.legs)
                trading_day_index = date_indexes[trading_date]
                days_held = max(0, trading_day_index - position.entry_day_index)
                leg_bars = _current_bars_for_legs(position, today)
                expiry_due = trading_date >= earliest_expiry
                marks_for_day = (
                    today
                    if not expiry_due or (trading_date == earliest_expiry and leg_bars is not None)
                    else {}
                )
                current_mark = _mark_position(position, marks_for_day, trading_date)
                daily_pnl += current_mark - position.previous_mark_to_market
                position.previous_mark_to_market = current_mark
                if trading_date <= earliest_expiry and leg_bars is not None:
                    position.last_joint_prices = {
                        leg.contract_id: (leg_bars[leg.contract_id].normalized_price, trading_date)
                        for leg in trade.legs
                    }
                force_reason = None
                if expiry_due:
                    force_reason = "EXPIRY"
                elif days_held >= self.config.max_holding_days:
                    force_reason = "MAX_HOLDING_PERIOD"

                if force_reason is not None:
                    exit_bars = leg_bars or {}
                    if force_reason == "EXPIRY" and (
                        trading_date > earliest_expiry or leg_bars is None
                    ):
                        position.last_prices = dict(position.last_joint_prices)
                        exit_bars = {}
                    daily_cost += _close_position(
                        position,
                        exit_bars,
                        trading_date,
                        days_held,
                        self.config,
                        force_reason,
                        signals.get((trade.target_contract_id, trading_date, source_type), None).z_score
                        if signals.get((trade.target_contract_id, trading_date, source_type), None)
                        else None,
                    )
                    position = None
                else:
                    pending_was_set = position.pending_exit_reason is not None
                    if pending_was_set and leg_bars is not None and all(
                        _is_liquid(bar, self.config) for bar in leg_bars.values()
                    ):
                        daily_cost += _close_position(
                            position,
                            leg_bars,
                            trading_date,
                            days_held,
                            self.config,
                            position.pending_exit_reason or "MEAN_REVERSION",
                            position.pending_exit_z_score,
                        )
                        position = None
                    elif not pending_was_set:
                        current_signal = signals.get((trade.target_contract_id, trading_date, source_type))
                        if leg_bars is None:
                            position.pending_exit_reason = "PEER_UNAVAILABLE"
                        elif (
                            current_signal is not None
                            and current_signal.z_score is not None
                            and abs(current_signal.z_score) <= self.config.exit_z
                        ):
                            position.pending_exit_reason = "MEAN_REVERSION"
                            position.pending_exit_z_score = current_signal.z_score

            if pending_entry is not None and position is None:
                signal = pending_entry.signal
                required_ids = (signal.contract_id,) + pending_entry.peer_contract_ids
                earliest_entry_expiry = min(contract_expiries[item] for item in required_ids)
                days_remaining_at_entry = (earliest_entry_expiry - trading_date).days
                if (
                    trading_date < earliest_entry_expiry
                    and days_remaining_at_entry >= self.config.minimum_days_to_expiry
                    and all(
                    contract_id in today for contract_id in required_ids
                    )
                ):
                    execution_bars = [today[contract_id] for contract_id in required_ids]
                    if any(not _is_liquid(bar, self.config) for bar in execution_bars):
                        rejections.append(
                            EntryRejection(
                                signal_date=signal.trade_date,
                                symbol=signal.symbol,
                                contract_id=signal.contract_id,
                                direction=signal.relative_direction,
                                z_score=signal.z_score,
                                entry_rejected_reason="INSUFFICIENT_LIQUIDITY",
                                source_type=source_type,
                            )
                        )
                        pending_entry = None
                    else:
                        target_bar = today[signal.contract_id]
                        peers = [today[contract_id] for contract_id in pending_entry.peer_contract_ids]
                        legs = build_trade_legs(target_bar, peers, signal.relative_direction, self.config)
                        for leg in legs:
                            leg.entry_cost = estimated_execution_cost(leg.entry_notional, self.config)
                        entry_cost = sum((leg.entry_cost for leg in legs), Decimal(0))
                        target_leg = next(leg for leg in legs if leg.contract_id == signal.contract_id)
                        peer_legs = [leg for leg in legs if leg.contract_id != signal.contract_id]
                        peer_notional = sum((leg.entry_notional for leg in peer_legs), Decimal(0))
                        peer_grams = sum(
                            (leg.contract_equivalents * leg.contract_size_grams for leg in peer_legs),
                            Decimal(0),
                        )
                        trade = Trade(
                            trade_id=f"BT-{len(trades) + 1:05d}",
                            target_symbol=signal.symbol,
                            target_expiry_date=signal.expiry_date,
                            target_contract_id=signal.contract_id,
                            peer_symbols=tuple(sorted({leg.symbol for leg in peer_legs})),
                            peer_contract_ids=tuple(leg.contract_id for leg in peer_legs),
                            entry_signal_date=signal.trade_date,
                            entry_date=trading_date,
                            exit_date=None,
                            entry_z_score=signal.z_score or Decimal(0),
                            exit_z_score=None,
                            direction=signal.relative_direction,
                            target_entry_price=target_leg.entry_price_per_gram,
                            target_exit_price=None,
                            peer_entry_value=peer_notional / peer_grams if peer_grams else Decimal(0),
                            peer_exit_value=None,
                            target_units=target_leg.contract_equivalents,
                            peer_units=tuple(leg.contract_equivalents for leg in peer_legs),
                            days_held=None,
                            exit_reason=None,
                            target_leg_gross_pnl=None,
                            peer_leg_gross_pnl=None,
                            gross_pnl=None,
                            transaction_cost=entry_cost,
                            net_pnl=None,
                            return_on_capital=None,
                            status="OPEN",
                            source_type=source_type,
                            source_file=signal.source_file,
                            legs=legs,
                        )
                        position = _OpenPosition(
                            trade=trade,
                            last_prices={
                                leg.contract_id: (today[leg.contract_id].normalized_price, trading_date)
                                for leg in legs
                            },
                            last_joint_prices={
                                leg.contract_id: (today[leg.contract_id].normalized_price, trading_date)
                                for leg in legs
                            },
                            entry_day_index=date_indexes[trading_date],
                        )
                        trades.append(trade)
                        daily_cost += entry_cost
                        pending_entry = None
                elif (
                    trading_date >= earliest_entry_expiry
                    or days_remaining_at_entry < self.config.minimum_days_to_expiry
                ):
                    rejections.append(
                        EntryRejection(
                            signal_date=signal.trade_date,
                            symbol=signal.symbol,
                            contract_id=signal.contract_id,
                            direction=signal.relative_direction,
                            z_score=signal.z_score,
                            entry_rejected_reason="EXPIRY_FILTER_FAILED",
                            source_type=source_type,
                        )
                    )
                    pending_entry = None

            if pending_entry is None and position is None:
                day_signals = sorted(
                    signals_by_date.get(trading_date, []),
                    key=lambda item: (item.symbol, item.expiry_date),
                )
                for signal in day_signals:
                    if signal.signal_status != "STRONG_RELATIVE_DEVIATION":
                        continue
                    if signal.z_score is None or abs(signal.z_score) < self.config.entry_z:
                        continue
                    if signal.relative_direction not in {"CHEAP", "EXPENSIVE"}:
                        continue
                    if signal.days_to_expiry < self.config.minimum_days_to_expiry:
                        rejections.append(
                            EntryRejection(
                                signal_date=trading_date,
                                symbol=signal.symbol,
                                contract_id=signal.contract_id,
                                direction=signal.relative_direction,
                                z_score=signal.z_score,
                                entry_rejected_reason="EXPIRY_FILTER_FAILED",
                                source_type=source_type,
                            )
                        )
                        continue
                    peer_ids = _peer_contracts_at_signal(signal, today)
                    if not peer_ids:
                        rejections.append(
                            EntryRejection(
                                signal_date=trading_date,
                                symbol=signal.symbol,
                                contract_id=signal.contract_id,
                                direction=signal.relative_direction,
                                z_score=signal.z_score,
                                entry_rejected_reason="PEER_UNAVAILABLE",
                                source_type=source_type,
                            )
                        )
                        continue
                    pending_entry = _PendingEntry(signal=signal, peer_contract_ids=peer_ids)
                    break

            if position is not None:
                # A newly opened position is entered at today's close, hence has zero same-close mark-to-market.
                if position.trade.entry_date == trading_date:
                    position.previous_mark_to_market = Decimal(0)

            ending_equity = starting_equity + daily_pnl - daily_cost
            capital = ending_equity
            equity.append(
                EquityPoint(
                    date=trading_date,
                    starting_equity=starting_equity,
                    daily_pnl=daily_pnl,
                    daily_cost=daily_cost,
                    daily_net_pnl=daily_pnl - daily_cost,
                    ending_equity=ending_equity,
                )
            )

        completed_dates = [bar.trade_date for bar in bars.values()]
        notes = [
            "Daily close is a simulation mark, not a verified executable intraday fill.",
            "Entry and ordinary exit fills use the next joint available trading date close after the observation.",
            "Expiry and maximum-holding exits are forced at the first observed close when the limit is reached; stale marks are used only if a leg has no close on that date.",
            "Volume and OpenInterest are liquidity proxies, not order-book depth.",
            "Sizing uses fractional contract-equivalent units to balance normalized notional; actual lot increments are not modeled.",
            "Peer baskets are fixed at the signal date and preserve exact Symbol+ExpiryDate identities.",
            "At most one position is open at a time; concurrent signals are not stacked.",
        ]
        if dataset_type.upper() in {"DEMO", "SYNTHETIC", "DEMO / SYNTHETIC DATA"}:
            dataset_type = "DEMO / SYNTHETIC DATA"
            notes.insert(0, "All source observations are synthetic demo data, not real MCX market evidence.")
        if not any(signal.signal_status == "STRONG_RELATIVE_DEVIATION" for signal in signals.values()):
            notes.append("No Stage 4 strong-deviation entry signal exists in this dataset; no trade opportunity is inferred.")
        if any(trade.status == "OPEN" for trade in trades):
            notes.append("Open positions are marked to the last available normalized close and remain unrealized at dataset end.")
        if pending_entry is not None:
            signal = pending_entry.signal
            rejections.append(
                EntryRejection(
                    signal_date=signal.trade_date,
                    symbol=signal.symbol,
                    contract_id=signal.contract_id,
                    direction=signal.relative_direction,
                    z_score=signal.z_score,
                    entry_rejected_reason="NO_NEXT_AVAILABLE_JOINT_DATE",
                    source_type=source_type,
                )
            )
        notes.extend(source_files)

        metrics = calculate_metrics(trades, equity, self.config.initial_capital)
        benchmark = calculate_benchmark(bars, equity, self.config)
        result = BacktestResult(
            dataset_type=dataset_type,
            dataset_start=min(completed_dates) if completed_dates else None,
            dataset_end=max(completed_dates) if completed_dates else None,
            initial_capital=self.config.initial_capital,
            configuration=self.config.to_dict(),
            trades=trades,
            rejected_entries=rejections,
            equity_curve=equity,
            benchmark=benchmark,
            metrics=metrics,
            data_quality_notes=notes,
            report={},
        )
        result.report = build_report(result)
        return result


def run_backtest(
    normalized_path: str | Path,
    signals_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    source_type: str = "DEMO",
    config: BacktestConfig | None = None,
) -> BacktestResult:
    selected_config = config or BacktestConfig.from_environment()
    bars, signals = load_backtest_inputs(normalized_path, signals_path, source_type)
    result = BacktestEngine(selected_config).run(
        bars,
        signals,
        dataset_type="DEMO / SYNTHETIC DATA" if source_type.upper() == "DEMO" else "REAL/HISTORICAL",
        source_files=(str(Path(normalized_path).resolve()), str(Path(signals_path).resolve())),
    )
    destination = (
        Path(output_dir).expanduser().resolve()
        if output_dir is not None
        else BacktestConfigPath.default_output_dir()
    )
    destination.mkdir(parents=True, exist_ok=True)
    stem = Path(signals_path).stem.removesuffix("_signals")
    prefix = destination / f"{stem}_backtest"
    trade_path = prefix.with_name(prefix.name + "_trades.json")
    equity_path = prefix.with_name(prefix.name + "_equity.json")
    benchmark_path = prefix.with_name(prefix.name + "_benchmark.json")
    report_path = prefix.with_name(prefix.name + "_report.json")
    trade_path.write_text(json.dumps(json_safe(result.trades), indent=2) + "\n", encoding="utf-8")
    equity_path.write_text(json.dumps(json_safe(result.equity_curve), indent=2) + "\n", encoding="utf-8")
    benchmark_path.write_text(json.dumps(json_safe(result.benchmark), indent=2) + "\n", encoding="utf-8")
    result.report["artifact_paths"] = {
        "report": str(report_path),
        "trades": str(trade_path),
        "equity": str(equity_path),
        "benchmark": str(benchmark_path),
    }
    write_report(result.report, report_path)
    return result


class BacktestConfigPath:
    @staticmethod
    def default_output_dir() -> Path:
        return Path(__file__).resolve().parents[3] / "data" / "backtests"