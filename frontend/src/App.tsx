import { useEffect, useState } from 'react';
import { api } from './lib/api';

function App() {
  const [backendStatus, setBackendStatus] = useState<string>('Checking connection...');

  useEffect(() => {
    api
      .getHealth()
      .then((data) => {
        if (data.status === 'ok') {
          setBackendStatus('Connected to backend: ' + data.message);
        } else {
          setBackendStatus('Backend responded with unknown status.');
        }
      })
      .catch(() => {
        setBackendStatus('Failed to connect to backend.');
      });
  }, []);

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white flex flex-col items-center justify-center p-6 text-center space-y-6">
      <div className="flex flex-col items-center justify-center space-y-4">
        <div className="w-16 h-16 rounded bg-gradient-to-br from-green-400 to-blue-600 flex items-center justify-center font-bold text-3xl text-black">
          A
        </div>
        <h1 className="text-4xl font-bold tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-gray-100 to-gray-500">
          AUREON
        </h1>
        <h2 className="text-xl text-gray-400">Commodity Derivatives Intelligence</h2>
      </div>
      
      <div className="bg-[#111] border border-gray-800 rounded-lg p-6 max-w-md w-full mt-8">
        <h3 className="text-lg font-semibold mb-2">System Initialized</h3>
        <p className={`text-sm ${backendStatus.includes('Connected') ? 'text-green-400' : 'text-yellow-400'}`}>
          {backendStatus}
        </p>
      </div>
    </div>
  );
}

export default App;
