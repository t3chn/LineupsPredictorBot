#!/usr/bin/env python3

import os
import subprocess
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_cron_monitoring():
    """Setup cron job to monitor /start command every 5 minutes"""
    try:
        script_path = os.path.abspath("monitor_start_command.py")
        log_path = os.path.abspath("start_command_monitor.log")
        
        cron_command = f"*/5 * * * * cd {os.path.dirname(script_path)} && python {script_path} >> {log_path} 2>&1"
        
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        current_crontab = result.stdout if result.returncode == 0 else ""
        
        if cron_command not in current_crontab:
            new_crontab = current_crontab + f"\n{cron_command}\n"
            
            process = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE, text=True)
            process.communicate(input=new_crontab)
            
            if process.returncode == 0:
                logger.info("✅ Cron monitoring setup successfully")
                logger.info(f"Monitor logs: {log_path}")
                return True
            else:
                logger.error("❌ Failed to setup cron monitoring")
                return False
        else:
            logger.info("✅ Cron monitoring already setup")
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to setup monitoring: {e}")
        return False

def create_systemd_service():
    """Create systemd service for continuous monitoring"""
    try:
        script_path = os.path.abspath("monitor_start_command.py")
        service_content = f"""[Unit]
Description=Fantasy Football Bot Start Command Monitor
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory={os.path.dirname(script_path)}
ExecStart=/usr/bin/python3 {script_path}
Restart=always
RestartSec=300

[Install]
WantedBy=multi-user.target
"""
        
        service_path = "/etc/systemd/system/bot-start-monitor.service"
        
        with open("bot-start-monitor.service", "w") as f:
            f.write(service_content)
        
        logger.info("✅ Created systemd service file: bot-start-monitor.service")
        logger.info("To install: sudo cp bot-start-monitor.service /etc/systemd/system/")
        logger.info("To enable: sudo systemctl enable bot-start-monitor.service")
        logger.info("To start: sudo systemctl start bot-start-monitor.service")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to create systemd service: {e}")
        return False

if __name__ == "__main__":
    logger.info("🔧 Setting up /start command monitoring...")
    
    cron_success = setup_cron_monitoring()
    service_success = create_systemd_service()
    
    if cron_success:
        logger.info("🎉 Monitoring setup complete!")
    else:
        logger.error("⚠️ Some monitoring setup failed")
