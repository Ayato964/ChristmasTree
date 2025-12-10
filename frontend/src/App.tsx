import React, { useState, useEffect, useRef } from 'react';
import './index.css';

// Components (will be extracted later if complex)
const SnowEffect = () => {
  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden" aria-hidden="true">
      {Array.from({ length: 50 }).map((_, i) => (
        <div
          key={i}
          className="absolute text-white text-opacity-80 animate-fall"
          style={{
            left: `${Math.random() * 100}vw`,
            top: '-20px',
            fontSize: `${Math.random() * 20 + 10}px`,
            animationDuration: `${Math.random() * 5 + 3}s`,
            animationDelay: `${Math.random() * 5}s`,
            animationIterationCount: 'infinite',
            animationTimingFunction: 'linear'
          }}
        >
          ❄
        </div>
      ))}
    </div>
  );
};

function App() {
  // Use current_tree.png as default to show latest state immediately
  const [treeUrl, setTreeUrl] = useState<string>(`/assets/current_tree.png?t=${Date.now()}`);
  const [loading, setLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);

  // WebSocket Connection
  useEffect(() => {
    // Dynamic WebSocket URL based on current host (handles localhost vs IP)
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.host;
    const wsUrl = `${wsProtocol}//${wsHost}/ws`; // Proxy forwards /ws -> backend

    let ws: WebSocket;

    const connect = () => {
      ws = new WebSocket(wsUrl);
      ws.onopen = () => console.log('Connected to WS');
      ws.onmessage = (event) => {
        if (event.data === 'update_tree') {
          // Force refresh current_tree.png
          setTreeUrl(`/assets/current_tree.png?t=${Date.now()}`);
          setLoading(false);
        }
      };
      ws.onclose = () => {
        console.log('WS Disconnected, retrying...');
        setTimeout(connect, 3000);
      };
    };

    connect();
    return () => {
      if (ws) ws.close();
    };
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const reader = new FileReader();
      reader.onloadend = () => {
        setPreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fileInputRef.current?.files?.[0]) return;

    setLoading(true);
    setUploadStatus(null);
    const formData = new FormData();
    formData.append('file', fileInputRef.current.files[0]);

    try {
      // Use relative path (proxied)
      const response = await fetch('/upload', {
        method: 'POST',
        body: formData,
      });
      const result = await response.json();
      if (result.status === 'success') {
        setUploadStatus('Decoration added!');
        setPreview(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
      } else {
        setUploadStatus('Failed: ' + result.message);
        setLoading(false);
      }
    } catch (error) {
      console.error(error);
      setUploadStatus('Error uploading image.');
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center p-4">
      <SnowEffect />

      <div className="glass w-full max-w-5xl rounded-3xl p-8 flex flex-col md:flex-row gap-8 z-10">

        {/* Tree Section */}
        <div className="flex-1 flex flex-col items-center justify-center relative min-h-[400px]">
          <h1 className="font-christmas text-5xl md:text-6xl text-christmas-gold drop-shadow-lg mb-8 text-center animate-pulse">
            Christmas Tree
          </h1>

          <div className="relative w-full aspect-square max-w-[500px] flex items-center justify-center p-4 border-2 border-white/20 rounded-2xl bg-black/20 backdrop-blur-sm shadow-inner transition-all duration-500 hover:scale-[1.02]">
            {/* Loading Overlay */}
            {loading && (
              <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/50 rounded-2xl">
                <div className="w-16 h-16 border-4 border-christmas-gold border-t-transparent rounded-full animate-spin"></div>
              </div>
            )}

            <img
              src={treeUrl}
              alt="Christmas Tree"
              className="w-full h-full object-contain drop-shadow-2xl transition-opacity duration-300"
              onError={(e) => console.error("Failed to load:", treeUrl)}
            />
          </div>
        </div>

        {/* Controls Section */}
        <div className="flex-1 flex flex-col justify-center">
          <div className="glass p-8 rounded-2xl bg-white/5 border border-white/10 shadow-xl">
            <h2 className="font-christmas text-4xl mb-2 text-center text-white">Decorate It!</h2>
            <p className="text-center text-gray-200 mb-8 font-light">
              Upload your "Mofumofu" to join the party.
            </p>

            <form onSubmit={handleUpload} className="flex flex-col gap-6">
              <div className="w-full">
                <label className="flex flex-col items-center justify-center w-full h-40 border-2 border-dashed border-white/30 rounded-xl cursor-pointer hover:bg-white/10 transition-colors group">
                  <div className="flex flex-col items-center justify-center pt-5 pb-6">
                    {preview ? (
                      <img src={preview} className="h-28 object-contain rounded-lg shadow-md" alt="Preview" />
                    ) : (
                      <>
                        <svg className="w-10 h-10 mb-3 text-gray-300 group-hover:text-white transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
                        <p className="mb-2 text-sm text-gray-300 group-hover:text-white"><span className="font-semibold">Click to upload</span></p>
                        <p className="text-xs text-gray-400">PNG or JPG</p>
                      </>
                    )}
                  </div>
                  <input ref={fileInputRef} type="file" className="hidden" accept="image/*" onChange={handleFileChange} />
                </label>
              </div>

              <button
                type="submit"
                disabled={loading || !preview}
                className="w-full py-4 bg-gradient-to-r from-red-600 to-red-800 text-white font-bold rounded-xl shadow-lg transform transition-all hover:scale-[1.02] active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-red-900/50"
              >
                {loading ? 'Decorating...' : '✨ Add Decoration ✨'}
              </button>

              {uploadStatus && (
                <div className={`text-center p-2 rounded-lg text-sm font-semibold ${uploadStatus.includes('Failed') ? 'bg-red-500/20 text-red-200' : 'bg-green-500/20 text-green-200'}`}>
                  {uploadStatus}
                </div>
              )}
            </form>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes fall {
          to { transform: translateY(105vh); }
        }
        .animate-fall {
            animation-name: fall;
        }
      `}</style>
    </div>
  );
}

export default App;
