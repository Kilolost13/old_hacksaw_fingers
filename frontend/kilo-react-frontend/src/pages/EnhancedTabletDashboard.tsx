import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import SpeechRecognition, { useSpeechRecognition } from 'react-speech-recognition';
import { FaMicrophone, FaMicrophoneSlash, FaCamera, FaPaperclip, FaCog, FaUser, FaBrain, FaBell, FaChartLine, FaLightbulb, FaTrophy } from 'react-icons/fa';
import { chatService } from '../services/chatService';
import { Message, DashboardStats, RealTimeUpdate, CoachingInsight } from '../types';
import { CameraCapture } from '../components/shared/CameraCapture';
import { Button } from '../components/shared/Button';
import { Card } from '../components/shared/Card';

const EnhancedTabletDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([
    { id: '1', role: 'ai', content: "Good morning! How can I help you today?", timestamp: new Date() }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [showCamera, setShowCamera] = useState(false);
  const [showVoiceInput, setShowVoiceInput] = useState(false);
  const [manualInputMode, setManualInputMode] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Enhanced state for tablet UI
  const [stats, setStats] = useState<DashboardStats>({
    totalMemories: 0,
    activeHabits: 0,
    completedGoals: 0,
    streakDays: 0,
    averageMood: 0,
    recentActivity: 0,
    activeGoals: 0,
    upcomingReminders: 0,
    monthlySpending: 0,
    insightsGenerated: 0,
    goalsProgress: 0
  });
  const [realTimeUpdates, setRealTimeUpdates] = useState<RealTimeUpdate[]>([]);
  const [insights, setInsights] = useState<CoachingInsight[]>([]);

  const {
    transcript,
    listening,
    resetTranscript,
    browserSupportsSpeechRecognition
  } = useSpeechRecognition();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (transcript && !listening) {
      setInput(transcript);
      handleVoiceSubmit(transcript);
    }
  }, [transcript, listening]);

  // Load dashboard data
  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      // Mock data - replace with actual API calls
      setStats({
        totalMemories: 1247,
        activeHabits: 5,
        completedGoals: 12,
        streakDays: 23,
        averageMood: 7.8,
        recentActivity: 45,
        activeGoals: 3,
        upcomingReminders: 2,
        monthlySpending: 1250.50,
        insightsGenerated: 89,
        goalsProgress: 68
      });

      setRealTimeUpdates([
        {
          id: '1',
          type: 'memory_added',
          message: 'New memory added to your knowledge base',
          timestamp: new Date().toISOString(),
          priority: 'medium'
        }
      ]);

      setInsights([
        {
          id: '1',
          type: 'motivation',
          title: 'Great Progress!',
          description: 'You\'ve maintained your exercise habit for 23 days straight!',
          message: 'You\'ve maintained your exercise habit for 23 days straight!',
          priority: 'high',
          actionable: true,
          createdAt: new Date().toISOString()
        }
      ]);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await chatService.sendMessage(input);
      const aiContent = typeof response === 'string'
        ? response
        : (response && typeof response === 'object' && 'message' in response)
          ? (response as { message?: string }).message || JSON.stringify(response)
          : JSON.stringify(response);
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'ai',
        content: aiContent,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, aiMessage]);
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'ai',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleVoiceSubmit = async (voiceText: string) => {
    if (!voiceText.trim()) return;
    setInput(voiceText);
    await sendMessage();
  };

  const startVoiceInput = () => {
    resetTranscript();
    SpeechRecognition.startListening({
      continuous: true,
      language: 'en-US'
    } as any);
    setShowVoiceInput(true);
  };

  const stopVoiceInput = () => {
    SpeechRecognition.stopListening();
    setShowVoiceInput(false);
  };

  const handleReceiptCapture = async (imageBlob: Blob) => {
    setShowCamera(false);
    // Handle receipt processing
    alert('Receipt captured! Processing...');
  };

  const quickActions = [
    { icon: '💊', label: 'MEDS', path: '/medications', color: 'bg-blue-500' },
    { icon: '🔔', label: 'REMINDERS', path: '/reminders', color: 'bg-green-500' },
    { icon: '💰', label: 'FINANCE', path: '/finance', color: 'bg-yellow-500' },
    { icon: '✓', label: 'HABITS', path: '/habits', color: 'bg-purple-500' },
    { icon: '📋', label: 'MEMORY', path: '/knowledge-graph', color: 'bg-red-500' }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 p-4">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-white flex items-center gap-3">
          {React.createElement(FaBrain as any, { className: 'text-blue-400 text-4xl' })}
          KILO AI MEMORY ASSISTANT
        </h1>
        <div className="flex items-center gap-4">
          <Button
            onClick={() => navigate('/admin')}
            variant="secondary"
            size="sm"
            className="flex items-center gap-2"
          >
            {React.createElement(FaUser as any, null)}
            Admin
          </Button>
          <Button
            onClick={() => navigate('/ui-comparison')}
            variant="primary"
            size="sm"
            className="flex items-center gap-2"
          >
            📱 UI COMPARISON
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Chat Area */}
        <div className="lg:col-span-2">
          <Card className="h-[600px] flex flex-col">
            <div className="flex-1 overflow-y-auto p-4 space-y-4" ref={messagesEndRef}>
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] p-4 rounded-2xl ${
                      message.role === 'user'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-900'
                    }`}
                  >
                    <p className="text-lg">{message.content}</p>
                    <p className="text-xs opacity-70 mt-2">
                      {message.timestamp.toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start">
                  <div className="bg-gray-100 p-4 rounded-2xl">
                    <div className="flex items-center gap-2">
                      <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
                      <span className="text-gray-600">AI is thinking...</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Input Area - Enhanced for tablet */}
            <div className="border-t border-gray-200 p-4">
              {!manualInputMode ? (
                <div className="flex gap-3">
                  <Button
                    onClick={listening ? stopVoiceInput : startVoiceInput}
                    variant={listening ? "primary" : "secondary"}
                    size="lg"
                    className="flex-1 h-16 text-xl flex items-center justify-center gap-3"
                  >
                    {listening ? React.createElement(FaMicrophone as any, { className: 'text-2xl' }) : React.createElement(FaMicrophoneSlash as any, { className: 'text-2xl' })}
                    {listening ? 'Listening...' : 'Tap to Speak'}
                  </Button>
                  <Button
                    onClick={() => setShowCamera(true)}
                    variant="secondary"
                    size="lg"
                    className="h-16 w-16 flex items-center justify-center text-2xl"
                  >
                    {React.createElement(FaCamera as any, null)}
                  </Button>
                  <Button
                    onClick={() => setManualInputMode(true)}
                    variant="outline"
                    size="lg"
                    className="h-16 px-6 flex items-center justify-center text-xl"
                  >
                    ✏️ Type
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                      placeholder="Type your message here..."
                      className="flex-1 p-4 text-xl border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <Button
                      onClick={sendMessage}
                      variant="primary"
                      size="lg"
                      disabled={!input.trim() || loading}
                      className="px-8 h-16 text-xl"
                    >
                      Send
                    </Button>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      onClick={() => setManualInputMode(false)}
                      variant="secondary"
                      size="sm"
                      className="flex items-center gap-2"
                    >
                      🎤 Voice
                    </Button>
                    <Button
                      onClick={() => setShowCamera(true)}
                      variant="secondary"
                      size="sm"
                      className="flex items-center gap-2"
                    >
                      {React.createElement(FaCamera as any, null)}
                      Camera
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      className="flex items-center gap-2"
                    >
                      {React.createElement(FaPaperclip as any, null)}
                      Attach
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </Card>
        </div>

        {/* Sidebar - Stats and Quick Actions */}
        <div className="space-y-6">
          {/* Quick Actions - Large tablet-friendly buttons */}
          <Card>
            <h3 className="text-xl font-semibold text-white mb-4">Quick Actions</h3>
            <div className="grid grid-cols-2 gap-3">
              {quickActions.map((action, index) => (
                <Button
                  key={index}
                  onClick={() => navigate(action.path)}
                  variant="secondary"
                  size="lg"
                  className={`h-20 flex flex-col items-center justify-center text-white ${action.color} hover:opacity-80`}
                >
                  <span className="text-3xl mb-1">{action.icon}</span>
                  <span className="text-sm font-medium">{action.label}</span>
                </Button>
              ))}
            </div>
          </Card>

          {/* Real-time Updates */}
          <Card>
            <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
              {React.createElement(FaBell as any, { className: 'text-yellow-400' })}
              Real-time Updates
            </h3>
            <div className="space-y-2">
              {realTimeUpdates.map((update) => (
                <div key={update.id} className="bg-blue-900/20 border border-blue-600/30 rounded-lg p-3">
                  <p className="text-sm text-blue-200">{update.message}</p>
                  <p className="text-xs text-blue-400 mt-1">
                    {new Date(update.timestamp).toLocaleTimeString()}
                  </p>
                </div>
              ))}
            </div>
          </Card>

          {/* AI Coaching */}
          <Card>
            <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
              {React.createElement(FaLightbulb as any, { className: 'text-purple-400' })}
              AI Coaching
            </h3>
            <div className="space-y-3">
              {insights.map((insight) => (
                <div key={insight.id} className="bg-purple-900/20 border border-purple-600/30 rounded-lg p-3">
                  <h4 className="font-semibold text-purple-200">{insight.title}</h4>
                  <p className="text-sm text-purple-300 mt-1">{insight.description}</p>
                </div>
              ))}
            </div>
          </Card>

          {/* Dashboard Stats */}
          <Card>
            <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
              {React.createElement(FaChartLine as any, { className: 'text-green-400' })}
              Dashboard Stats
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-gray-800/50 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-green-400">{stats.totalMemories}</div>
                <div className="text-xs text-gray-400">Memories</div>
              </div>
              <div className="bg-gray-800/50 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-blue-400">{stats.activeHabits}</div>
                <div className="text-xs text-gray-400">Active Habits</div>
              </div>
              <div className="bg-gray-800/50 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-yellow-400">{stats.streakDays}</div>
                <div className="text-xs text-gray-400">Day Streak</div>
              </div>
              <div className="bg-gray-800/50 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-purple-400">{stats.goalsProgress}%</div>
                <div className="text-xs text-gray-400">Goals Progress</div>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Camera Modal */}
      {showCamera && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white p-6 rounded-2xl max-w-md w-full mx-4">
            <CameraCapture onCapture={handleReceiptCapture} onClose={() => setShowCamera(false)} />
            <Button
              onClick={() => setShowCamera(false)}
              variant="secondary"
              className="w-full mt-4"
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default EnhancedTabletDashboard;