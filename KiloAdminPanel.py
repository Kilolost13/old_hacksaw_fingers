import tkinter as tk
from tkinter import messagebox
import subprocess
import webbrowser
import os
import logging

# Setup logging
logging.basicConfig(
    filename='/home/brain_ai/kilo_admin_gui.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configuration
PORTAL_URL = "http://192.168.68.56:30002"
K3S_NAMESPACE = "kilo-guardian"
KUBECONFIG = "/home/brain_ai/.kube/hp-k3s.yaml"

class KiloAdminPanel:
    def __init__(self, root):
        self.root = root
        self.root.title("🛡️ KILO ADMIN CONTROL")
        self.root.geometry("450x450")
        self.root.configure(bg="#050505")
        
        # Style
        self.bg_color = "#050505"
        self.fg_color = "#39FF14" # Zombie Green
        
        # Font Fallbacks
        self.font_title = ("monospace", 18, "bold")
        self.font_btn = ("monospace", 11, "bold")
        self.font_status = ("monospace", 10)
        
        self.setup_ui()
        self.update_pod_status()

    def setup_ui(self):
        # Title
        tk.Label(
            self.root, 
            text="🛡️ KILO SYSTEM MASTER CONTROL", 
            font=self.font_title,
            bg=self.bg_color, 
            fg=self.fg_color,
            pady=20
        ).pack()

        # Start Button
        self.start_btn = tk.Button(
            self.root, text="🚀 START ALL (15+ PODS)", command=self.start_system,
            bg="#004d00", fg="white", font=self.font_btn, width=25, height=2, bd=1
        )
        self.start_btn.pack(pady=5)

        # Stop Button
        self.stop_btn = tk.Button(
            self.root, text="🛑 STOP ALL SERVICES", command=self.stop_system,
            bg="#4d0000", fg="white", font=self.font_btn, width=25, height=2, bd=1
        )
        self.stop_btn.pack(pady=5)

        # Restart Button
        self.restart_btn = tk.Button(
            self.root, text="🔄 RESTART ALL (HOT RELOAD)", command=self.restart_system,
            bg="#333300", fg="white", font=self.font_btn, width=25, height=2, bd=1
        )
        self.restart_btn.pack(pady=5)

        # Launch Admin Button
        self.launch_btn = tk.Button(
            self.root, text="🌐 OPEN PORTAL", command=self.launch_admin,
            bg="#00004d", fg="white", font=self.font_btn, width=25, height=2, bd=1
        )
        self.launch_btn.pack(pady=5)

        # Status Bar
        self.status_var = tk.StringVar(value="Status: Syncing with Cluster...")
        self.status_label = tk.Label(
            self.root, textvariable=self.status_var, bg="#111111", fg=self.fg_color,
            font=self.font_status, height=2
        )
        self.status_label.pack(side="bottom", fill="x")

    def run_kubectl(self, args):
        cmd = ["kubectl", "--kubeconfig", KUBECONFIG, "-n", K3S_NAMESPACE] + args
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr)
        return result.stdout

    def update_pod_status(self):
        try:
            output = self.run_kubectl(["get", "pods", "--no-headers"])
            lines = [l for l in output.strip().split('\n') if l and "kilo" in l]
            running = sum(1 for l in lines if "Running" in l)
            total = len(lines)
            self.status_var.set(f"Status: {running}/{total} Pods Online")
            self.status_label.config(fg="#ff4444" if running == 0 else "#ffff44" if running < total else self.fg_color)
        except:
            self.status_var.set("Status: Connection Lost")
        self.root.after(5000, self.update_pod_status) # Auto-refresh every 5s

    def start_system(self):
        self.status_var.set("Status: Scaling up all deployments...")
        self.root.update()
        try:
            self.run_kubectl(["scale", "deployment", "--all", "--replicas=1"])
            messagebox.showinfo("Kilo Admin", "Scale-up command sent to all services.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def stop_system(self):
        if not messagebox.askyesno("Confirm", "Stop all services?"): return
        self.status_var.set("Status: Scaling down all deployments...")
        self.root.update()
        try:
            self.run_kubectl(["scale", "deployment", "--all", "--replicas=0"])
            messagebox.showinfo("Kilo Admin", "All services stopped.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def restart_system(self):
        self.status_var.set("Status: Restarting all deployments...")
        self.root.update()
        try:
            self.run_kubectl(["rollout", "restart", "deployment", "--all"])
            messagebox.showinfo("Kilo Admin", "Rolling restart initiated.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def launch_admin(self):
        webbrowser.open(PORTAL_URL)

if __name__ == "__main__":
    root = tk.Tk()
    app = KiloAdminPanel(root)
    root.mainloop()