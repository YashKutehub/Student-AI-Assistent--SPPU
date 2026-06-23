import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Paperclip, Bot, User, X, Loader2, Plus, MessageSquare, Trash2, Menu, ChevronLeft, Database, Zap, Download, Volume2, Play, Pause, RefreshCw } from 'lucide-react';

const API_URL = "http://localhost:8000";

function App() {
  const [isSyncing, setIsSyncing] = useState(false);
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedImage, setSelectedImage] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [isSidebarOpen, setSidebarOpen] = useState(false); // default closed on mobile
  const [isRagEnabled, setIsRagEnabled] = useState(true);
  const [showMobileMenu, setShowMobileMenu] = useState(false); // mobile mode toggle sheet

  const [playingId, setPlayingId] = useState(null);
  const [isAudioPaused, setIsAudioPaused] = useState(false);

  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const currentAudioRef = useRef(null);

  // Detect if we're on mobile
  const isMobile = () => window.innerWidth < 768;

  useEffect(() => {
    // On desktop, open sidebar by default
    if (!isMobile()) setSidebarOpen(true);

    const savedSessions = localStorage.getItem('sppu_chat_sessions');
    if (savedSessions) {
      const parsed = JSON.parse(savedSessions);
      setSessions(parsed);
      if (parsed.length > 0) {
        loadSession(parsed[0].id, parsed);
      } else {
        createNewSession();
      }
    } else {
      createNewSession();
    }
  }, []);

  useEffect(() => {
    if (sessions.length > 0) {
      localStorage.setItem('sppu_chat_sessions', JSON.stringify(sessions));
    }
  }, [sessions]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const createNewSession = () => {
    const newSession = {
      id: Date.now(),
      title: "New Chat",
      timestamp: new Date().toISOString(),
      messages: [{
        id: 'init',
        text: "Hello! I'm your SPPU Student Assistant. Ready to study? Ask me anything!",
        sender: 'ai',
        sources: [],
        mode: 'general'
      }]
    };
    setSessions(prev => [newSession, ...prev]);
    setCurrentSessionId(newSession.id);
    setMessages(newSession.messages);
    setInput("");
    setSidebarOpen(false); // always close sidebar after action on mobile
  };

  const loadSession = (id, sessionList = sessions) => {
    const session = sessionList.find(s => s.id === id);
    if (session) {
      setCurrentSessionId(id);
      setMessages(session.messages);
      setSidebarOpen(false);

      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
        setPlayingId(null);
        setIsAudioPaused(false);
      }
    }
  };

  const deleteSession = (e, id) => {
    e.stopPropagation();
    const updatedSessions = sessions.filter(s => s.id !== id);
    setSessions(updatedSessions);
    localStorage.setItem('sppu_chat_sessions', JSON.stringify(updatedSessions));
    if (updatedSessions.length === 0) {
      createNewSession();
    } else if (id === currentSessionId) {
      loadSession(updatedSessions[0].id, updatedSessions);
    }
  };

  const updateCurrentSessionMessages = (newMessages) => {
    setMessages(newMessages);
    setSessions(prev => prev.map(session => {
      if (session.id === currentSessionId) {
        let newTitle = session.title;
        if (session.title === "New Chat" && newMessages.length > 1) {
          const firstUserMsg = newMessages.find(m => m.sender === 'user');
          if (firstUserMsg) {
            newTitle = firstUserMsg.text.slice(0, 30) + (firstUserMsg.text.length > 30 ? "..." : "");
          }
        }
        return { ...session, messages: newMessages, title: newTitle };
      }
      return session;
    }));
  };

  const handleImageSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedImage(file);
      setPreviewUrl(URL.createObjectURL(file));
    }
  };

  const clearImage = () => {
    setSelectedImage(null);
    setPreviewUrl(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleSend = async () => {
    if ((!input.trim() && !selectedImage) || isLoading) return;

    const userMessage = {
      id: Date.now(),
      text: input,
      sender: 'user',
      image: previewUrl
    };

    const updatedMessages = [...messages, userMessage];
    updateCurrentSessionMessages(updatedMessages);
    setInput("");
    setIsLoading(true);

    try {
      const recentHistory = updatedMessages.slice(-4).map(msg =>
        `${msg.sender === 'user' ? 'Student' : 'Assistant'}: ${msg.text}`
      ).join('\n');

      const formData = new FormData();
      formData.append('question', userMessage.text || "Analyze this image");
      formData.append('history', recentHistory);
      formData.append('use_rag', isRagEnabled);

      if (selectedImage) {
        formData.append('file', selectedImage);
      }

      clearImage();

      const response = await axios.post(`${API_URL}/chat`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      const aiMessageId = Date.now() + 1;
      const aiMessage = {
        id: aiMessageId,
        text: response.data.answer,
        sender: 'ai',
        sources: response.data.sources || [],
        mode: response.data.mode,
        audio_url: null,
        isAudioLoading: false
      };

      updateCurrentSessionMessages([...updatedMessages, aiMessage]);
    } catch (error) {
      console.error(error);
      const errorMessage = {
        id: Date.now() + 1,
        text: "⚠️ Error: Could not connect to the Assistant. Is your backend running?",
        sender: 'ai',
        isError: true
      };
      updateCurrentSessionMessages([...updatedMessages, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const updateSpecificMessage = (msgId, updates) => {
    setMessages(prev => prev.map(m => m.id === msgId ? { ...m, ...updates } : m));
    setSessions(prev => prev.map(session => {
      if (session.id === currentSessionId) {
        return { ...session, messages: session.messages.map(m => m.id === msgId ? { ...m, ...updates } : m) };
      }
      return session;
    }));
  };

  const playAudio = (id, audioUrl) => {
    const audio = new Audio(audioUrl);
    currentAudioRef.current = audio;
    setPlayingId(id);
    setIsAudioPaused(false);
    audio.play();
    audio.onended = () => {
      setPlayingId(null);
      setIsAudioPaused(false);
    };
  };

  const handleListen = async (msg) => {
    if (playingId === msg.id) {
      if (currentAudioRef.current.paused) {
        currentAudioRef.current.play();
        setIsAudioPaused(false);
      } else {
        currentAudioRef.current.pause();
        setIsAudioPaused(true);
      }
      return;
    }

    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
    }

    if (msg.audio_url) {
      playAudio(msg.id, msg.audio_url);
      return;
    }

    updateSpecificMessage(msg.id, { isAudioLoading: true });

    try {
      const res = await axios.post(`${API_URL}/speak`, { text: msg.text }, {
        responseType: 'blob'
      });
      const audioUrl = URL.createObjectURL(res.data);
      updateSpecificMessage(msg.id, { audio_url: audioUrl, isAudioLoading: false });
      playAudio(msg.id, audioUrl);
    } catch (err) {
      console.error("Audio fetch failed", err);
      updateSpecificMessage(msg.id, { isAudioLoading: false });
      alert("Failed to generate audio.");
    }
  };

  const exportChat = () => {
    if (messages.length <= 1) {
      alert("No conversation to export yet!");
      return;
    }
    const currentSession = sessions.find(s => s.id === currentSessionId);
    const title = currentSession ? currentSession.title.replace(/[^a-z0-9]/gi, '_').toLowerCase() : 'sppu_study_session';

    let chatContent = `# SPPU AI Assistant - Study Session\nDate: ${new Date().toLocaleString()}\nTopic: ${title}\n\n---\n\n`;

    messages.forEach(msg => {
      if (msg.id === 'init') return;
      const senderName = msg.sender === 'user' ? '🧑‍🎓 Student' : '🤖 SPPU Assistant';
      chatContent += `### ${senderName}\n${msg.text}\n\n`;
      if (msg.sources && msg.sources.length > 0) {
        chatContent += `*Sources used: ${msg.sources.join(', ')}*\n\n`;
      }
      chatContent += `---\n\n`;
    });

    const blob = new Blob([chatContent], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${title}_notes.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const getMessageStyle = (msg) => {
    if (msg.sender === 'user') return 'bg-blue-600 text-white rounded-tr-none';
    if (msg.isError) return 'bg-red-500/10 border border-red-500/20 text-red-200';
    return msg.mode === 'rag'
      ? 'bg-slate-800/80 border border-cyan-500/30 text-cyan-50 shadow-[0_0_15px_rgba(6,182,212,0.1)] rounded-tl-none'
      : 'bg-slate-800/80 border border-orange-500/30 text-orange-50 shadow-[0_0_15px_rgba(249,115,22,0.1)] rounded-tl-none';
  };

  const handleSyncNotices = async () => {
    setIsSyncing(true);
    try {
      const res = await axios.post(`${API_URL}/sync-notices`);
      alert(res.data.message);
    } catch (err) {
      console.error(err);
      alert("Failed to sync with SPPU servers.");
    } finally {
      setIsSyncing(false);
    }
  };

  return (
    <div className="flex h-screen w-screen bg-slate-900 text-white overflow-hidden font-sans relative">

      {/* ── SIDEBAR OVERLAY (mobile only) ── */}
      <AnimatePresence>
        {isSidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 z-30 md:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* ── SIDEBAR ── */}
      {/* On mobile: fixed overlay. On desktop: static flex column. */}
      <motion.aside
        initial={false}
        animate={{ x: isSidebarOpen ? 0 : '-100%' }}
        transition={{ type: 'tween', duration: 0.22 }}
        className="fixed md:static top-0 left-0 h-full z-40 md:z-auto
                   w-64 md:w-64
                   bg-slate-900 border-r border-white/10
                   flex flex-col shrink-0
                   md:translate-x-0"
        style={{ transform: undefined }} // let motion handle it on mobile; on md+ we use CSS
      >
        {/* Close button inside sidebar (mobile only) */}
        <button
          onClick={() => setSidebarOpen(false)}
          className="md:hidden absolute top-3 right-3 p-1.5 rounded-lg hover:bg-white/10 text-slate-400"
        >
          <X size={18} />
        </button>

        <div className="p-4 flex flex-col gap-4 h-full pt-12 md:pt-4">
          <button
            onClick={createNewSession}
            className="flex items-center gap-3 bg-blue-600 hover:bg-blue-500 text-white px-4 py-3 rounded-lg transition-all shadow-lg hover:shadow-blue-500/20 font-medium w-full"
          >
            <Plus size={20} />
            <span>New Chat</span>
          </button>

          <div className="flex-1 overflow-y-auto space-y-2 pr-1">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 mt-2 pl-2">Recent Chats</h3>
            {sessions.map((session) => (
              <div
                key={session.id}
                onClick={() => loadSession(session.id)}
                className={`group flex items-center justify-between p-3 rounded-lg cursor-pointer transition-all ${
                  currentSessionId === session.id
                    ? 'bg-slate-800 text-white border border-white/10'
                    : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
                }`}
              >
                <div className="flex items-center gap-3 overflow-hidden">
                  <MessageSquare size={16} className={currentSessionId === session.id ? 'text-cyan-400' : 'text-slate-500'} />
                  <span className="truncate text-sm">{session.title}</span>
                </div>
                <button
                  onClick={(e) => deleteSession(e, session.id)}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400 transition-opacity shrink-0"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>

          <div className="pt-4 border-t border-white/10 flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-cyan-500 to-blue-500 flex items-center justify-center shrink-0">
              <User size={16} className="text-white" />
            </div>
            <div className="flex-1 overflow-hidden">
              <p className="text-sm font-medium truncate">Saurav Wankhade</p>
              <p className="text-xs text-emerald-400">Final Year - SPPU</p>
            </div>
          </div>
        </div>
      </motion.aside>

      {/* ── MAIN CHAT ── */}
      <main className="flex-1 flex flex-col h-full relative bg-slate-900/50 min-w-0">

        {/* ── HEADER ── */}
        <header className="h-14 md:h-16 border-b border-white/10 bg-slate-900/80 backdrop-blur-md flex items-center justify-between px-3 md:px-4 z-10 shrink-0 gap-2">

          {/* Left: hamburger + title */}
          <div className="flex items-center gap-2 min-w-0">
            <button
              onClick={() => setSidebarOpen(!isSidebarOpen)}
              className="p-2 hover:bg-white/5 rounded-lg text-slate-400 transition-colors shrink-0"
            >
              <Menu size={20} />
            </button>
            <h1 className="font-bold text-sm tracking-wide flex items-center gap-2 truncate">
              <span className="hidden xs:inline">SPPU Assistant</span>
              <span className="xs:hidden">SPPU</span>
              <span className="bg-slate-800 text-[10px] px-1.5 py-0.5 rounded text-slate-300 border border-white/5 shrink-0">v2.2</span>
            </h1>
          </div>

          {/* Right: action buttons */}
          <div className="flex items-center gap-1.5 md:gap-3 shrink-0">

            {/* Sync — icon only on mobile */}
            <button
              onClick={handleSyncNotices}
              disabled={isSyncing}
              className="flex items-center gap-1.5 px-2 md:px-3 py-1.5 rounded-md text-xs font-medium text-emerald-400 hover:text-emerald-300 hover:bg-emerald-900/30 border border-emerald-500/30 transition-all disabled:opacity-50"
            >
              <RefreshCw size={14} className={isSyncing ? "animate-spin" : ""} />
              <span className="hidden md:inline">{isSyncing ? "Syncing..." : "Live Sync"}</span>
            </button>

            {/* Export — icon only on mobile */}
            <button
              onClick={exportChat}
              className="flex items-center gap-1.5 px-2 md:px-3 py-1.5 rounded-md text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800 border border-transparent hover:border-white/10 transition-all"
            >
              <Download size={16} />
              <span className="hidden md:inline">Export</span>
            </button>

            {/* Mode toggle — compact on mobile */}
            <div className="flex items-center bg-slate-800 p-0.5 rounded-lg border border-white/5">
              <button
                onClick={() => setIsRagEnabled(true)}
                className={`flex items-center gap-1 px-2 md:px-3 py-1.5 rounded-md text-xs font-medium transition-all ${isRagEnabled ? 'bg-cyan-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
                title="RAG Mode"
              >
                <Database size={13} />
                <span className="hidden sm:inline">RAG</span>
              </button>
              <button
                onClick={() => setIsRagEnabled(false)}
                className={`flex items-center gap-1 px-2 md:px-3 py-1.5 rounded-md text-xs font-medium transition-all ${!isRagEnabled ? 'bg-orange-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
                title="General Mode"
              >
                <Zap size={13} />
                <span className="hidden sm:inline">Gen</span>
              </button>
            </div>
          </div>
        </header>

        {/* ── MESSAGES ── */}
        <div className="flex-1 overflow-y-auto p-3 md:p-6 lg:p-8 space-y-4 md:space-y-6 scroll-smooth">
          <AnimatePresence>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex gap-2 md:gap-4 ${msg.sender === 'user' ? 'justify-end' : 'justify-start md:max-w-3xl md:mx-auto w-full'}`}
              >
                {msg.sender === 'ai' && (
                  <div className="flex flex-col items-center gap-2 mt-1 shrink-0">
                    <div className={`w-7 h-7 md:w-8 md:h-8 rounded-full flex items-center justify-center border border-white/10 ${msg.mode === 'rag' ? 'bg-cyan-900/50 text-cyan-400' : 'bg-orange-900/50 text-orange-400'}`}>
                      {msg.mode === 'rag' ? <Database size={14} /> : <Zap size={14} />}
                    </div>

                    {msg.id !== 'init' && (
                      <button
                        onClick={() => handleListen(msg)}
                        disabled={msg.isAudioLoading}
                        className={`w-6 h-6 md:w-7 md:h-7 rounded-full flex items-center justify-center transition-all border ${
                          playingId === msg.id
                            ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-400'
                            : 'bg-slate-800 border-white/5 text-slate-400 hover:text-white hover:bg-slate-700'
                        }`}
                        title="Listen"
                      >
                        {msg.isAudioLoading ? (
                          <Loader2 size={10} className="animate-spin text-cyan-400" />
                        ) : playingId === msg.id && !isAudioPaused ? (
                          <Pause size={10} fill="currentColor" />
                        ) : (
                          <Play size={10} className="ml-0.5" fill="currentColor" />
                        )}
                      </button>
                    )}
                  </div>
                )}

                <div className={`space-y-2 min-w-0 ${msg.sender === 'user' ? 'max-w-[85%] md:max-w-[75%]' : 'flex-1'}`}>

                  {playingId === msg.id && !isAudioPaused && (
                    <motion.div
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      className="inline-flex items-center gap-1.5 bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-[10px] font-bold px-2 py-0.5 rounded-full mb-1 animate-pulse"
                    >
                      <Volume2 size={10} /> Speaking...
                    </motion.div>
                  )}

                  <div className={`p-3 md:p-4 rounded-2xl text-sm leading-relaxed shadow-sm ${getMessageStyle(msg)}`}>
                    {msg.image && (
                      <img src={msg.image} alt="Uploaded" className="max-w-full w-full h-auto rounded-lg mb-3 border border-white/10" />
                    )}
                    <div className="whitespace-pre-wrap break-words">
                      {msg.text.split('**').map((part, i) =>
                        i % 2 === 1
                          ? <strong key={i} className={msg.mode === 'rag' ? "text-cyan-300 font-bold" : "text-orange-300 font-bold"}>{part}</strong>
                          : part
                      )}
                    </div>
                  </div>

                  {/* Sources */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pl-1 mt-1">
                      {msg.sources.map((src, idx) => {
                        const isPageCited = src.includes('[Pg.');
                        const fileNameOnly = src.split(' [Pg.')[0];
                        const pageMatch = src.match(/\[Pg\. (\d+)\]/);
                        const pageNumber = pageMatch ? pageMatch[1] : null;
                        const viewUrl = `${API_URL}/view/${encodeURIComponent(fileNameOnly)}${pageNumber ? `#page=${pageNumber}` : ''}`;

                        return (
                          <a
                            key={idx}
                            href={viewUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[10px] bg-slate-800/50 hover:bg-slate-700 text-slate-400 hover:text-cyan-300 px-2 py-1 rounded border border-white/5 hover:border-cyan-500/30 truncate max-w-[200px] md:max-w-[280px] cursor-pointer transition-all flex items-center gap-1"
                            title={`View ${fileNameOnly} at Page ${pageNumber || 1}`}
                          >
                            {isPageCited ? '📍' : '📄'} <span className="truncate">{src}</span>
                          </a>
                        );
                      })}
                    </div>
                  )}

                  {msg.sender === 'ai' && !msg.sources?.length && msg.mode === 'general' && (
                    <div className="text-[10px] text-slate-500 pl-1 italic">Generated using General Knowledge</div>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {isLoading && (
            <div className="md:max-w-3xl md:mx-auto w-full flex gap-3">
              <div className="w-7 h-7 rounded-full bg-slate-800 flex items-center justify-center shrink-0 border border-white/10">
                <Bot size={14} className="text-slate-400 animate-pulse" />
              </div>
              <div className="flex items-center gap-2 text-slate-400 text-sm pt-1">
                <Loader2 size={15} className="animate-spin text-cyan-400" />
                Generating Intelligence...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* ── INPUT ── */}
        <div className="p-3 md:p-4 bg-slate-900 border-t border-white/10 z-20 safe-area-bottom">
          <div className="md:max-w-3xl md:mx-auto w-full">
            <AnimatePresence>
              {previewUrl && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="flex items-center gap-3 mb-2 bg-slate-800 p-2 rounded-lg w-fit border border-white/10"
                >
                  <img src={previewUrl} alt="Preview" className="w-9 h-9 rounded object-cover" />
                  <span className="text-xs text-slate-300 max-w-[160px] truncate">{selectedImage?.name}</span>
                  <button onClick={clearImage} className="p-1 hover:bg-white/10 rounded-full text-slate-400 hover:text-white">
                    <X size={14} />
                  </button>
                </motion.div>
              )}
            </AnimatePresence>

            <div className={`flex items-center gap-2 bg-slate-800 px-2 py-2 rounded-xl border transition-all shadow-lg ${isRagEnabled ? 'focus-within:border-cyan-500/50 border-white/10' : 'focus-within:border-orange-500/50 border-white/10'}`}>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleImageSelect}
                accept="image/*"
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className={`p-1.5 rounded-lg transition-all shrink-0 ${selectedImage ? 'text-cyan-400 bg-cyan-400/10' : 'text-slate-400 hover:text-white hover:bg-slate-700'}`}
              >
                <Paperclip size={18} />
              </button>

              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder={isRagEnabled ? "Ask about your syllabus..." : "Ask anything..."}
                className="flex-1 bg-transparent text-sm text-white placeholder-slate-500 outline-none min-w-0 py-1"
                disabled={isLoading}
              />

              <button
                onClick={handleSend}
                disabled={isLoading || (!input.trim() && !selectedImage)}
                className={`p-2 rounded-lg text-white shadow-lg transition-all shrink-0 ${isRagEnabled ? 'bg-cyan-600 hover:bg-cyan-500' : 'bg-orange-600 hover:bg-orange-500'} disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                <Send size={16} />
              </button>
            </div>

            <div className="text-center mt-1.5">
              <p className="text-[10px] text-slate-600">
                Mode: <span className={isRagEnabled ? "text-cyan-400 font-bold" : "text-orange-500 font-bold"}>
                  {isRagEnabled ? "RAG (Files)" : "General (Internet)"}
                </span>
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
