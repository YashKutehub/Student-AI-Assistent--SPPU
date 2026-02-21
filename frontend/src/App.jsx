import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Paperclip, Bot, User, X, Loader2, Plus, MessageSquare, Trash2, Menu, ChevronLeft, Database, Zap, Download } from 'lucide-react';

const API_URL = "http://localhost:8000"; 

function App() {
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedImage, setSelectedImage] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [isSidebarOpen, setSidebarOpen] = useState(true);
  const [isRagEnabled, setIsRagEnabled] = useState(true);

  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
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
        mode: 'general' // Default greeting is general
      }]
    };
    setSessions(prev => [newSession, ...prev]);
    setCurrentSessionId(newSession.id);
    setMessages(newSession.messages);
    setInput("");
    if (window.innerWidth < 768) setSidebarOpen(false);
  };

  const loadSession = (id, sessionList = sessions) => {
    const session = sessionList.find(s => s.id === id);
    if (session) {
      setCurrentSessionId(id);
      setMessages(session.messages);
      if (window.innerWidth < 768) setSidebarOpen(false);
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
      const recentHistory = updatedMessages.slice(-6).map(msg => 
        `${msg.sender === 'user' ? 'Student' : 'Assistant'}: ${msg.text}`
      ).join('\n');

      const formData = new FormData();
      formData.append('question', userMessage.text || "Analyze this image");
      formData.append('history', recentHistory);
      formData.append('use_rag', isRagEnabled);
      
      let endpoint = `${API_URL}/chat`;
      if (selectedImage) {
        formData.append('file', selectedImage);
      }

      const response = await axios.post(endpoint, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      const aiMessage = {
        id: Date.now() + 1,
        text: response.data.answer,
        sender: 'ai',
        sources: response.data.sources || [],
        mode: response.data.mode // Get Mode from Backend
      };

      updateCurrentSessionMessages([...updatedMessages, aiMessage]);
      clearImage();

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

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // --- HELPER: GET STYLE BASED ON MODE ---
  const getMessageStyle = (msg) => {
    if (msg.sender === 'user') return 'bg-blue-600 text-white rounded-tr-none';
    if (msg.isError) return 'bg-red-500/10 border border-red-500/20 text-red-200';
    
    // AI LOGIC:
    if (msg.mode === 'rag') {
      // CYAN STYLE for RAG
      return 'bg-slate-800/80 border border-cyan-500/30 text-cyan-50 shadow-[0_0_15px_rgba(6,182,212,0.1)] rounded-tl-none'; 
    } else {
      // ORANGE STYLE for General
      return 'bg-slate-800/80 border border-orange-500/30 text-orange-50 shadow-[0_0_15px_rgba(249,115,22,0.1)] rounded-tl-none';
    }
  };

  return (
    <div className="flex h-screen w-screen bg-slate-900 text-white overflow-hidden font-sans">
      
      {/* SIDEBAR */}
      <motion.aside 
        initial={{ width: 0, opacity: 0 }}
        animate={{ width: isSidebarOpen ? 260 : 0, opacity: isSidebarOpen ? 1 : 0 }}
        className="bg-slate-900 border-r border-white/10 flex flex-col shrink-0 relative"
      >
        <div className="p-4 flex flex-col gap-4 h-full">
          <button 
            onClick={createNewSession}
            className="flex items-center gap-3 bg-blue-600 hover:bg-blue-500 text-white px-4 py-3 rounded-lg transition-all shadow-lg hover:shadow-blue-500/20 font-medium w-full"
          >
            <Plus size={20} />
            <span>New Chat</span>
          </button>

          <div className="flex-1 overflow-y-auto space-y-2 custom-scrollbar pr-2">
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
                  className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400 transition-opacity"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>

          <div className="pt-4 border-t border-white/10 flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-linear-to-tr from-cyan-500 to-blue-500 flex items-center justify-center">
              <User size={16} className="text-white" />
            </div>
            <div className="flex-1 overflow-hidden">
              <p className="text-sm font-medium truncate">Student User</p>
              <p className="text-xs text-emerald-400">Pro Plan (LLama-3)</p>
            </div>
          </div>
        </div>
      </motion.aside>

      {/* MAIN CHAT */}
      <main className="flex-1 flex flex-col h-full relative bg-slate-900/50">
        
        {/* HEADER */}
        <header className="h-16 border-b border-white/10 bg-slate-900/50 backdrop-blur-md flex items-center justify-between px-4 z-10 shrink-0">
          <div className="flex items-center gap-3">
            <button 
              onClick={() => setSidebarOpen(!isSidebarOpen)}
              className="p-2 hover:bg-white/5 rounded-lg text-slate-400 transition-colors"
            >
              {isSidebarOpen ? <ChevronLeft size={20}/> : <Menu size={20}/>}
            </button>
            <div className="flex flex-col">
              <h1 className="font-bold text-sm tracking-wide flex items-center gap-2">
                SPPU Assistant <span className="bg-slate-800 text-[10px] px-2 py-0.5 rounded text-slate-300 border border-white/5">v2.2</span>
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2 bg-slate-800 p-1 rounded-lg border border-white/5">
            <button 
              onClick={() => setIsRagEnabled(true)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                isRagEnabled ? 'bg-cyan-600 text-white shadow' : 'text-slate-400 hover:text-white'
              }`}
            >
              <Database size={14} />
              RAG Mode
            </button>
            <button 
              onClick={() => setIsRagEnabled(false)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                !isRagEnabled ? 'bg-orange-600 text-white shadow' : 'text-slate-400 hover:text-white'
              }`}
            >
              <Zap size={14} />
              General
            </button>
          </div>
        </header>

        {/* MESSAGES */}
        <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6 scroll-smooth z-10">
          <AnimatePresence>
            {messages.map((msg) => (
              <motion.div 
                key={msg.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex gap-4 ${msg.sender === 'user' ? 'justify-end' : 'justify-start max-w-3xl mx-auto w-full'}`}
              >
                {msg.sender === 'ai' && (
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 border border-white/10 mt-1 ${
                    msg.mode === 'rag' ? 'bg-cyan-900/50 text-cyan-400' : 'bg-orange-900/50 text-orange-400'
                  }`}>
                    {msg.mode === 'rag' ? <Database size={16} /> : <Zap size={16} />}
                  </div>
                )}

                <div className={`space-y-2 ${msg.sender === 'user' ? 'max-w-[80%]' : 'flex-1 min-w-0'}`}>
                  
                  {/* DYNAMIC MESSAGE STYLE */}
                  <div className={`p-4 rounded-2xl text-sm leading-relaxed shadow-sm ${getMessageStyle(msg)}`}>
                    {msg.image && (
                      <img src={msg.image} alt="Uploaded" className="max-w-md w-full h-auto rounded-lg mb-3 border border-white/10" />
                    )}
                    <div className="whitespace-pre-wrap markdown-body">
                      {msg.text.split('**').map((part, i) => 
                        i % 2 === 1 ? <strong key={i} className={msg.mode === 'rag' ? "text-cyan-300 font-bold" : "text-orange-300 font-bold"}>{part}</strong> : part
                      )}
                    </div>
                  </div>

                  {msg.sources && msg.sources.length > 0 && (
                      <div className="flex flex-wrap gap-2 pl-1 mt-1">
                        {msg.sources.map((src, idx) => (
                          <a 
                            key={idx} 
                            href={`${API_URL}/download/${encodeURIComponent(src)}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            download
                            className="group text-[10px] bg-slate-800/50 hover:bg-slate-700 text-slate-400 hover:text-cyan-300 px-2 py-1 rounded border border-white/5 hover:border-cyan-500/30 truncate max-w-[250px] cursor-pointer transition-all flex items-center gap-1.5 shadow-sm"
                            title={`Download ${src}`}
                          >
                            📄 {src}
                            <Download size={10} className="opacity-0 group-hover:opacity-100 transition-opacity" />
                          </a>
                        ))}
                      </div>
                    )}
                  {msg.sender === 'ai' && !msg.sources?.length && msg.mode === 'general' && (
                     <div className="text-[10px] text-slate-500 pl-1 italic">
                        Generated using General Knowledge (No Files Used)
                     </div>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
          
          {isLoading && (
            <div className="max-w-3xl mx-auto w-full flex gap-4">
               <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center shrink-0 border border-white/10">
                  <Bot size={16} className="text-slate-400 animate-pulse" />
               </div>
               <div className="flex items-center gap-2 text-slate-400 text-sm pt-2">
                 <Loader2 size={16} className="animate-spin text-cyan-400" />
                 Thinking...
               </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* INPUT */}
        <div className="p-4 bg-slate-900 border-t border-white/10 z-20">
          <div className="max-w-3xl mx-auto w-full">
            <AnimatePresence>
              {previewUrl && (
                <motion.div 
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="flex items-center gap-3 mb-3 bg-slate-800 p-2 rounded-lg w-fit border border-white/10"
                >
                  <img src={previewUrl} alt="Preview" className="w-10 h-10 rounded object-cover" />
                  <span className="text-xs text-slate-300 max-w-[200px] truncate">{selectedImage.name}</span>
                  <button onClick={clearImage} className="p-1 hover:bg-white/10 rounded-full text-slate-400 hover:text-white">
                    <X size={14} />
                  </button>
                </motion.div>
              )}
            </AnimatePresence>

            <div className={`flex items-center gap-3 bg-slate-800 p-2.5 rounded-xl border transition-all shadow-lg ${
                isRagEnabled ? 'focus-within:border-cyan-500/50 border-white/10' : 'focus-within:border-orange-500/50 border-white/10'
            }`}>
              <input 
                type="file" 
                ref={fileInputRef}
                onChange={handleImageSelect}
                accept="image/*"
                className="hidden"
              />
              <button 
                onClick={() => fileInputRef.current?.click()}
                className={`p-2 rounded-lg transition-all ${
                  selectedImage ? 'text-cyan-400 bg-cyan-400/10' : 'text-slate-400 hover:text-white hover:bg-slate-700'
                }`}
              >
                <Paperclip size={20} />
              </button>

              <input 
                type="text" 
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder={isRagEnabled ? "Ask about your syllabus (RAG Mode)..." : "Ask anything (General Mode)..."}
                className="flex-1 bg-transparent text-sm text-white placeholder-slate-500 outline-none min-w-0"
                disabled={isLoading}
              />

              <button 
                onClick={handleSend}
                disabled={isLoading || (!input.trim() && !selectedImage)}
                className={`p-2 rounded-lg text-white shadow-lg transition-all ${
                    isRagEnabled ? 'bg-cyan-600 hover:bg-cyan-500' : 'bg-orange-600 hover:bg-orange-500'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                <Send size={18} />
              </button>
            </div>
            <div className="text-center mt-2">
              <p className="text-[10px] text-slate-600">
                Mode: <span className={isRagEnabled ? "text-cyan-400 font-bold" : "text-orange-500 font-bold"}>{isRagEnabled ? "RAG (Files)" : "General (Internet)"}</span>
              </p>
            </div>
          </div>
        </div>

      </main>
    </div>
  );
}

export default App;