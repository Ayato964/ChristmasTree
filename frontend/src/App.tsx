import React, { useState, useEffect, useRef } from 'react';
import './index.css';

// --- Components ---

const SnowEffect = () => {
  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden z-50" aria-hidden="true">
      {Array.from({ length: 50 }).map((_, i) => (
        <div
          key={i}
          className="absolute text-blue-300 text-opacity-80 animate-fall"
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

interface AdminPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onRestore: (filename: string) => void;
  onRollback: (steps: number) => void;
}

const AdminPanel: React.FC<AdminPanelProps> = ({ isOpen, onClose, onRestore, onRollback }) => {
  const [history, setHistory] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchHistory();
    }
  }, [isOpen]);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const res = await fetch('/admin/history'); // Proxied
      const data = await res.json();
      setHistory(data.history || []);
    } catch (e) {
      console.error("Failed to fetch history", e);
    }
    setLoading(false);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4">
      <div className="bg-gray-900 w-full max-w-4xl h-[80vh] rounded-3xl shadow-2xl flex flex-col border border-white/10 overflow-hidden">

        {/* Header */}
        <div className="p-6 border-b border-white/10 flex justify-between items-center bg-gray-800/50">
          <h2 className="text-2xl font-bold text-christmas-gold">🎄 Admin Control Panel</h2>
          <div className="flex gap-4">
            <button
              onClick={() => onRollback(0)} // Rollback 0 means "go to generated image before current"? No, rollback(1) is usually what we want.
              // Wait, if current is index 0, rollback(1) goes to index 1.
              className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg font-semibold transition-colors shadow-lg"
            >
              Undo Last Change
            </button>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg transition-colors"
            >
              Close
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="text-white text-center">Loading history...</div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
              {history.map((filename, idx) => (
                <div key={filename} className="group relative bg-gray-800 rounded-xl overflow-hidden border border-white/5 hover:border-christmas-gold/50 transition-all">
                  <div className="aspect-square relative">
                    <img
                      src={`/tree-assets/history/${filename}`}
                      alt={filename}
                      className="w-full h-full object-cover"
                    />
                    {idx === 0 && (
                      <div className="absolute top-2 right-2 bg-green-500 text-white text-xs px-2 py-1 rounded-full font-bold shadow-md">
                        CURRENT
                      </div>
                    )}
                  </div>
                  <div className="p-3">
                    <p className="text-xs text-gray-400 truncate mb-3" title={filename}>{filename}</p>
                    <button
                      onClick={() => onRestore(filename)}
                      className="w-full py-2 bg-blue-600/20 hover:bg-blue-600 text-blue-200 hover:text-white rounded-lg text-sm font-semibold transition-all"
                    >
                      Restore This Version
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

function App() {
  const [treeUrl, setTreeUrl] = useState<string>(`/tree-assets/current_tree.png?t=${Date.now()}`);
  const [loading, setLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);

  // Admin State
  const [isAdminOpen, setIsAdminOpen] = useState(false);
  const keyBuffer = useRef<string>("");

  // WebSocket Connection
  useEffect(() => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.host;
    const wsUrl = `${wsProtocol}//${wsHost}/ws`;

    let ws: WebSocket;

    const connect = () => {
      ws = new WebSocket(wsUrl);
      ws.onopen = () => console.log('Connected to WS');
      ws.onmessage = (event) => {
        if (event.data === 'update_tree') {
          // Force refresh
          setTreeUrl(`/tree-assets/current_tree.png?t=${Date.now()}`);
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

  // Secret Code Listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore modifier keys and non-printable keys (except specific ones we might need, but here we just need numbers and !)
      if (e.key.length > 1) return;

      keyBuffer.current += e.key;

      // Keep buffer small
      if (keyBuffer.current.length > 20) {
        keyBuffer.current = keyBuffer.current.slice(-20);
      }

      // Check for exact string "964963!!"
      if (keyBuffer.current.endsWith("964963!!")) {
        setIsAdminOpen(true);
        keyBuffer.current = ""; // Reset
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
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
      const response = await fetch('/upload', { method: 'POST', body: formData });
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

  const handleRestore = async (filename: string) => {
    try {
      await fetch('/admin/restore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename })
      });
      // UI update will happen via WebSocket
    } catch (e) {
      alert("Restore failed");
    }
  };

  const handleRollback = async (steps: number) => {
    // Determine steps. "Undo Last" implies we want to go back to the previous one.
    // If we are at index 0, we want index 1. So steps=1.
    // My previous assumption in backend was "rollback(steps) -> target_index = steps".
    // So if I pass 1, it targets history[1]. This is correct for "Undo".
    try {
      await fetch('/admin/rollback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ steps: 1 })
      });
    } catch (e) {
      alert("Rollback failed");
    }
  }

  return (
    <div className="relative w-full h-[100dvh] flex flex-col md:flex-row overflow-hidden bg-white">
      <SnowEffect />
      <AdminPanel
        isOpen={isAdminOpen}
        onClose={() => setIsAdminOpen(false)}
        onRestore={handleRestore}
        onRollback={handleRollback}
      />

      {/* Left Panel: Tree */}
      <div className="w-full md:w-1/2 h-1/2 md:h-full flex flex-col items-center justify-center relative bg-white z-10 md:border-r border-b md:border-b-0 border-gray-100 p-4">

        <div className="relative w-full h-full flex items-center justify-center p-2 md:p-8 transition-all duration-500">
          {/* Loading Overlay */}
          {loading && (
            <div className="absolute inset-0 z-20 flex items-center justify-center bg-white/50 backdrop-blur-sm rounded-3xl">
              <div className="w-16 h-16 border-4 border-christmas-gold border-t-transparent rounded-full animate-spin"></div>
            </div>
          )}

          <img
            src={treeUrl}
            alt="Christmas Tree"
            className="w-full h-full object-contain drop-shadow-2xl transition-opacity duration-300 filter saturate-110"
            onError={() => console.error("Failed to load:", treeUrl)}
          />

          {/* Download Button Overlay - Bottom Right of Tree Panel */}
          <a
            href={treeUrl}
            download={`christmas_tree_${Date.now()}.png`}
            className="absolute bottom-4 right-4 p-3 bg-white/80 hover:bg-white text-christmas-red border border-christmas-red rounded-full font-bold shadow-sm hover:shadow-md transition-all z-30"
            title="Download"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
          </a>
        </div>
      </div>

      {/* Right Panel: Controls */}
      <div className="w-full md:w-1/2 h-1/2 md:h-full flex flex-col justify-center items-center bg-gray-50 p-6 md:p-12 z-20 shadow-[-10px_0_30px_-15px_rgba(0,0,0,0.1)] overflow-y-auto">
        <div className="w-full max-w-lg bg-white p-6 md:p-10 rounded-3xl shadow-xl border border-gray-100">
          <h2 className="font-christmas text-4xl md:text-5xl mb-4 text-center text-gray-800">Decorate It!</h2>
          <p className="text-center text-gray-500 mb-6 md:mb-10 font-normal text-lg">
            Upload your "Mofumofu" to join the party.
          </p>

          <form onSubmit={handleUpload} className="flex flex-col gap-6">
            <div className="w-full">
              <label className="flex flex-col items-center justify-center w-full h-56 border-2 border-dashed border-gray-300 rounded-2xl cursor-pointer hover:bg-gray-50 hover:border-christmas-red transition-all group relative overflow-hidden">
                <div className="flex flex-col items-center justify-center pt-5 pb-6 z-10">
                  {preview ? (
                    <img src={preview} className="h-44 object-contain shadow-lg rounded-md" alt="Preview" />
                  ) : (
                    <>
                      <div className="w-16 h-16 mb-4 rounded-full bg-blue-50 flex items-center justify-center group-hover:bg-blue-100 transition-colors">
                        <svg className="w-8 h-8 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
                      </div>
                      <p className="mb-2 text-lg text-gray-600 font-medium group-hover:text-gray-800">Click to upload image</p>
                      <p className="text-sm text-gray-400">PNG or JPG supported</p>
                    </>
                  )}
                </div>
                <input ref={fileInputRef} type="file" className="hidden" accept="image/*" onChange={handleFileChange} />
              </label>
            </div>

            <button
              type="submit"
              disabled={loading || !preview}
              className="w-full py-5 bg-christmas-red hover:bg-red-700 text-white text-xl font-bold rounded-2xl shadow-lg hover:shadow-xl transform transition-all active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3"
            >
              {loading ? (
                <>Decorating...</>
              ) : (
                <><span>✨</span> Add Decoration <span>✨</span></>
              )}
            </button>

            {uploadStatus && (
              <div className={`text-center p-3 rounded-xl text-base font-medium ${uploadStatus.includes('Failed') ? 'bg-red-50 text-red-600 border border-red-100' : 'bg-green-50 text-green-700 border border-green-100'}`}>
                {uploadStatus}
              </div>
            )}
          </form>
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
