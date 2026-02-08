import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { FaShieldAlt, FaVideo, FaSatellite, FaPlane, FaExclamationTriangle, FaLock, FaWifi } from 'react-icons/fa';
import { Button } from '../components/shared/Button';
import { Card } from '../components/shared/Card';
import { WebcamMonitor } from '../components/shared/WebcamMonitor';
import api from '../services/api';
import { useDeviceDetection } from '../utils/deviceDetection';

const GuardianControl: React.FC = () => {
  const navigate = useNavigate();
  const { deviceInfo, features } = useDeviceDetection();
  const [activeTab, setActiveTab] = useState<'security' | 'drone' | 'mesh' | 'vpn'>('security');
  const [alerts, setAlerts] = useState<any[]>([]);
  const [status, setStatus] = useState<any>({
    drone: 'Standby',
    mesh: 'Active',
    security: 'Armed',
    vpn: 'Connected'
  });

  useEffect(() => {
    fetchGuardianStatus();
  }, []);

  const fetchGuardianStatus = async () => {
    try {
      // These would call the guardian service via the gateway
      // Since we added 'guardian' to the gateway, we can call /api/guardian/health
      const response = await api.get('/guardian/health').catch(() => ({ data: { status: 'offline' } }));
      if (response.data.status === 'ok') {
        // Fetch real alerts if available
        const alertsRes = await api.get('/guardian/alerts').catch(() => ({ data: { alerts: [] } }));
        setAlerts(alertsRes.data.alerts || []);
      }
    } catch (error) {
      console.error('Failed to fetch guardian status:', error);
    }
  };

  return (
    <div className="min-h-screen zombie-gradient p-6">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-3xl font-bold text-zombie-green terminal-glow flex items-center gap-3">
            <FaShieldAlt className="text-4xl" /> GUARDIAN CONTROL
          </h1>
          <span className="text-xs px-2 py-1 rounded-full bg-dark-border text-red-500 border border-red-500 animate-pulse">
            HIGH SECURITY ZONE
          </span>
        </div>
        <Button onClick={() => navigate('/')} variant="secondary" size="sm">
          ← BACK TO DASHBOARD
        </Button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
        <button
          onClick={() => setActiveTab('security')}
          className={`flex items-center gap-2 px-6 py-3 rounded-t-lg font-bold transition-all ${
            activeTab === 'security' ? 'bg-zombie-green text-dark-bg' : 'bg-dark-border text-zombie-green hover:bg-zombie-green/10'
          }`}
        >
          <FaVideo /> SECURITY
        </button>
        <button
          onClick={() => setActiveTab('drone')}
          className={`flex items-center gap-2 px-6 py-3 rounded-t-lg font-bold transition-all ${
            activeTab === 'drone' ? 'bg-zombie-green text-dark-bg' : 'bg-dark-border text-zombie-green hover:bg-zombie-green/10'
          }`}
        >
          <FaPlane /> DRONE FPV
        </button>
        <button
          onClick={() => setActiveTab('mesh')}
          className={`flex items-center gap-2 px-6 py-3 rounded-t-lg font-bold transition-all ${
            activeTab === 'mesh' ? 'bg-zombie-green text-dark-bg' : 'bg-dark-border text-zombie-green hover:bg-zombie-green/10'
          }`}
        >
          <FaSatellite /> MESH NETWORK
        </button>
        <button
          onClick={() => setActiveTab('vpn')}
          className={`flex items-center gap-2 px-6 py-3 rounded-t-lg font-bold transition-all ${
            activeTab === 'vpn' ? 'bg-zombie-green text-dark-bg' : 'bg-dark-border text-zombie-green hover:bg-zombie-green/10'
          }`}
        >
          <FaLock /> VPN MANAGER
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Main Content Area */}
        <div className="lg:col-span-3">
          {activeTab === 'security' && (
            <div className="space-y-6">
              <Card className="bg-dark-card border-zombie-green">
                <h2 className="text-xl font-bold text-zombie-green mb-4 flex items-center gap-2">
                  <FaVideo /> LIVE SECURITY FEED
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="aspect-video bg-black rounded-lg border border-dark-border overflow-hidden relative">
                    <WebcamMonitor floating={false} widthClass="w-full" heightClass="h-full" />
                    <div className="absolute top-2 left-2 bg-red-600 text-white text-xs px-2 py-1 rounded animate-pulse">
                      REC: CAM-01 (HOST)
                    </div>
                  </div>
                  <div className="aspect-video bg-black rounded-lg border border-dark-border flex items-center justify-center text-gray-600 flex-col gap-2">
                    <FaVideo className="text-4xl" />
                    <span>CAM-02 (EXTERNAL) - OFFLINE</span>
                  </div>
                </div>
              </Card>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card>
                  <h3 className="text-lg font-bold text-zombie-green mb-3">INTRUSION DETECTION</h3>
                  <div className="space-y-2">
                    <div className="flex justify-between p-2 bg-dark-bg border border-dark-border rounded">
                      <span className="text-gray-400">Rate Limiter:</span>
                      <span className="text-green-400 font-mono">ACTIVE</span>
                    </div>
                    <div className="flex justify-between p-2 bg-dark-bg border border-dark-border rounded">
                      <span className="text-gray-400">Honeypot:</span>
                      <span className="text-green-400 font-mono">0 HITS</span>
                    </div>
                    <div className="flex justify-between p-2 bg-dark-bg border border-dark-border rounded">
                      <span className="text-gray-400">Log IDS:</span>
                      <span className="text-green-400 font-mono">MONITORING</span>
                    </div>
                  </div>
                </Card>
                <Card>
                  <h3 className="text-lg font-bold text-zombie-green mb-3">SYSTEM ACTIONS</h3>
                  <div className="grid grid-cols-2 gap-2">
                    <Button variant="danger" size="sm">PANIC RESET</Button>
                    <Button variant="secondary" size="sm">EXPORT LOGS</Button>
                    <Button variant="primary" size="sm" className="col-span-2">ARM SECURITY SYSTEM</Button>
                  </div>
                </Card>
              </div>
            </div>
          )}

          {activeTab === 'drone' && (
            <Card className="h-[600px] flex flex-col p-0 overflow-hidden bg-black">
              <div className="bg-dark-border p-4 flex justify-between items-center border-b border-zombie-green">
                <h2 className="text-xl font-bold text-zombie-green flex items-center gap-2">
                  <FaPlane /> DRONE MISSION CONTROL (FPV)
                </h2>
                <div className="flex gap-2">
                  <span className="px-2 py-1 bg-blue-900 text-blue-200 text-xs rounded">SIMULATION MODE</span>
                  <span className="px-2 py-1 bg-red-900 text-red-200 text-xs rounded">GEOFENCE ACTIVE</span>
                </div>
              </div>
              <div className="flex-1 bg-gray-900 relative">
                {/* Embed the unified drone control if possible, otherwise show placeholder */}
                <iframe 
                  src="/api/guardian/static/drone-control.html" 
                  className="w-full h-full border-none"
                  title="Drone Control"
                  onError={(e) => {
                    console.error('Failed to load drone control iframe');
                  }}
                />
                <div className="absolute inset-0 pointer-events-none border-2 border-zombie-green/20">
                  <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-32 h-32 border border-zombie-green/30 rounded-full"></div>
                  <div className="absolute top-1/2 left-0 right-0 h-px bg-zombie-green/20"></div>
                  <div className="absolute top-0 bottom-0 left-1/2 w-px bg-zombie-green/20"></div>
                </div>
              </div>
            </Card>
          )}

          {activeTab === 'mesh' && (
            <Card className="h-[600px] flex flex-col p-0 overflow-hidden bg-black">
               <div className="bg-dark-border p-4 flex justify-between items-center border-b border-zombie-green">
                <h2 className="text-xl font-bold text-zombie-green flex items-center gap-2">
                  <FaSatellite /> MESHTASTIC TRACKER
                </h2>
                <span className="px-2 py-1 bg-green-900 text-green-200 text-xs rounded">LORA ACTIVE</span>
              </div>
              <iframe 
                  src="/api/guardian/static/meshtastic-tracker.html" 
                  className="w-full h-full border-none"
                  title="Mesh Tracker"
                />
            </Card>
          )}

          {activeTab === 'vpn' && (
            <Card className="h-[600px] flex flex-col p-0 overflow-hidden bg-black">
               <div className="bg-dark-border p-4 flex justify-between items-center border-b border-zombie-green">
                <h2 className="text-xl font-bold text-zombie-green flex items-center gap-2">
                  <FaLock /> VPN & NETWORK MANAGER
                </h2>
                <span className="px-2 py-1 bg-blue-900 text-blue-200 text-xs rounded">ENCRYPTED</span>
              </div>
              <iframe 
                  src="/api/guardian/static/vpn-manager.html" 
                  className="w-full h-full border-none"
                  title="VPN Manager"
                />
            </Card>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <Card>
            <h3 className="text-lg font-bold text-zombie-green mb-4 flex items-center gap-2">
              <FaExclamationTriangle className="text-yellow-500" /> SYSTEM ALERTS
            </h3>
            <div className="space-y-3">
              {alerts.length === 0 ? (
                <div className="text-center py-4 text-gray-500 italic border border-dashed border-dark-border rounded">
                  No active threats detected
                </div>
              ) : (
                alerts.map((alert, idx) => (
                  <div key={idx} className="p-3 bg-red-900/20 border border-red-600 rounded text-sm text-red-200">
                    <div className="font-bold flex justify-between">
                      <span>{alert.type}</span>
                      <span className="text-xs opacity-50">{new Date(alert.timestamp).toLocaleTimeString()}</span>
                    </div>
                    <p className="mt-1">{alert.message}</p>
                  </div>
                ))
              )}
            </div>
          </Card>

          <Card>
            <h3 className="text-lg font-bold text-zombie-green mb-4">GUARDIAN STATUS</h3>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Security Pod:</span>
                <span className="text-green-500 font-bold font-mono">ONLINE</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Drone Plugin:</span>
                <span className="text-blue-400 font-bold font-mono">STANDBY</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Mesh Gateway:</span>
                <span className="text-green-500 font-bold font-mono">CONNECTED</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">VPN Tunnel:</span>
                <span className="text-green-500 font-bold font-mono">STABLE</span>
              </div>
            </div>
            <hr className="my-4 border-dark-border" />
            <Button variant="secondary" size="sm" className="w-full" onClick={fetchGuardianStatus}>
              REFRESH STATUS
            </Button>
          </Card>

          <Card className="bg-yellow-900/10 border-yellow-600/30">
            <h3 className="text-sm font-bold text-yellow-500 mb-2 flex items-center gap-2">
              <FaWifi /> NETWORK SCANNER
            </h3>
            <div className="text-xs text-gray-400 space-y-1">
              <p>Scanning local mesh...</p>
              <div className="w-full bg-dark-bg h-1 rounded overflow-hidden">
                <div className="bg-yellow-500 h-full w-2/3 animate-pulse"></div>
              </div>
              <p className="mt-2">Found 3 nodes in range</p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default GuardianControl;
