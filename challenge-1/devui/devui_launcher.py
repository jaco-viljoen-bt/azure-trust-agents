#!/usr/bin/env python3
"""
Azure Trust Agents - DevUI Launcher

This script provides a comprehensive interface for launching the Microsoft Agent Framework DevUI
with all the agents and workflows from the Azure Trust Agents Challenge 1.

Usage:
    python devui_launcher.py --mode directory      # Launch with directory discovery
    python devui_launcher.py --mode agents         # Launch with individual agents only
    python devui_launcher.py --mode workflow       # Launch with workflow only
    python devui_launcher.py --mode all            # Launch with all entities in-memory (default)
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, List

# Add the parent directory to the path to import agents and workflow
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

def check_environment():
    """Check if required environment variables are set"""
    required_vars = [
        "AI_FOUNDRY_PROJECT_ENDPOINT",
        "MODEL_DEPLOYMENT_NAME",
        "COSMOS_ENDPOINT",
        "COSMOS_KEY"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these variables in your .env file or environment.")
        print("See .env.example for reference.")
        return False
    
    print("✅ All required environment variables are set")
    return True

def launch_directory_mode(port: int = 8080):
    """Launch DevUI with directory-based discovery"""
    from agent_framework.devui import serve
    
    print(f"🚀 Launching DevUI in directory discovery mode on port {port}")
    print(f"📂 Scanning directory: {current_dir}")
    print(f"🌐 Access at: http://localhost:{port}")
    
    # Launch DevUI with directory discovery
    serve(entities_dir=str(current_dir), port=port, auto_open=True)

def launch_agents_mode(port: int = 8081):
    """Launch DevUI with agents only"""
    from agent_framework.devui import serve
    
    # Import agents
    try:
        from customer_data_agent import agent as customer_agent
        from risk_analyser_agent import agent as risk_agent
        from compliance_report_agent import agent as compliance_agent
        
        agents = [customer_agent, risk_agent, compliance_agent]
        
        print(f"🚀 Launching DevUI with {len(agents)} agents on port {port}")
        print("🤖 Available agents:")
        for agent in agents:
            print(f"   - {agent.name}")
        print(f"🌐 Access at: http://localhost:{port}")
        
        serve(entities=agents, port=port, auto_open=True)
        
    except ImportError as e:
        print(f"❌ Error importing agents: {e}")
        sys.exit(1)

def launch_workflow_mode(port: int = 8082):
    """Launch DevUI with workflows only"""
    from agent_framework.devui import serve
    
    # Import workflows
    try:
        from fraud_detection_workflow import workflow
        from fraud_detection_workflow_chal2 import workflow as workflow_chal2
        
        workflows = [workflow, workflow_chal2]
        
        print(f"🚀 Launching DevUI with fraud detection workflows on port {port}")
        for wf in workflows:
            print(f"🔄 Workflow: {wf.name}")
        print(f"🌐 Access at: http://localhost:{port}")
        
        serve(entities=workflows, port=port, auto_open=True)
        
    except ImportError as e:
        print(f"❌ Error importing workflow: {e}")
        sys.exit(1)

def launch_all_mode(port: int = 8080):
    """Launch DevUI with all entities in-memory"""
    from agent_framework.devui import serve
    
    # Import all entities
    try:
        from customer_data_agent import agent as customer_agent
        from risk_analyser_agent import agent as risk_agent
        from compliance_report_agent import agent as compliance_agent
        from fraud_detection_workflow import workflow
        from fraud_detection_workflow_chal2 import workflow as workflow_chal2
        
        entities = [customer_agent, risk_agent, compliance_agent, workflow, workflow_chal2]
        
        print(f"🚀 Launching DevUI with all entities on port {port}")
        print("🤖 Available entities:")
        for entity in entities:
            if hasattr(entity, 'name'):
                entity_type = "🔄 Workflow" if "workflow" in entity.__class__.__name__.lower() else "🤖 Agent"
                print(f"   {entity_type}: {entity.name}")
        print(f"🌐 Access at: http://localhost:{port}")
        print("\n💡 You can interact with:")
        print("   • Individual agents for specific tasks")
        print("   • Challenge 1: 3-step fraud detection workflow")
        print("   • Challenge 2: 4-executor parallel workflow (Compliance + Fraud Alert)")
        print("   • Test different transaction IDs (TX1001, TX2002, TX1012, etc.)")
        
        serve(entities=entities, port=port, auto_open=True)
        
    except ImportError as e:
        print(f"❌ Error importing entities: {e}")
        print("Make sure all agent and workflow modules are properly configured.")
        sys.exit(1)

def main():
    """Main function to parse arguments and launch DevUI"""
    parser = argparse.ArgumentParser(
        description="Azure Trust Agents DevUI Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Launch all entities (default)
  %(prog)s --mode directory          # Use directory discovery
  %(prog)s --mode agents --port 8081 # Launch agents only on port 8081
  %(prog)s --mode workflow           # Launch workflow only
  %(prog)s --mode all --port 8080    # Launch all entities on port 8080

Environment Variables Required:
  AI_FOUNDRY_PROJECT_ENDPOINT   - Azure AI Foundry project endpoint
  MODEL_DEPLOYMENT_NAME         - Model deployment name
  COSMOS_ENDPOINT              - Cosmos DB endpoint
  COSMOS_KEY                   - Cosmos DB key

Optional:
  AZURE_AI_CONNECTION_ID       - Azure AI Search connection ID
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["directory", "agents", "workflow", "all"],
        default="all",
        help="Launch mode (default: all)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to run the server on (default: 8080)"
    )
    
    parser.add_argument(
        "--no-env-check",
        action="store_true",
        help="Skip environment variable validation"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    
    print("=" * 60)
    print("🏦 Azure Trust Agents - Challenge 1 DevUI")
    print("=" * 60)
    
    # Check environment variables unless skipped
    if not args.no_env_check and not check_environment():
        sys.exit(1)
    
    # Change to the DevUI directory
    os.chdir(current_dir)
    
    try:
        if args.mode == "directory":
            launch_directory_mode(args.port)
        elif args.mode == "agents":
            launch_agents_mode(args.port)
        elif args.mode == "workflow":
            launch_workflow_mode(args.port)
        elif args.mode == "all":
            launch_all_mode(args.port)
            
    except KeyboardInterrupt:
        print("\n👋 DevUI stopped by user")
    except Exception as e:
        print(f"❌ Error launching DevUI: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()