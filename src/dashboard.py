"""
Flask monitoring dashboard for Pflug Law Lead Qualifier.
Simple web interface to monitor lead processing status.
"""

import logging
from datetime import datetime
from flask import Flask, render_template, jsonify

from .config import load_config
from .main import processing_history

logger = logging.getLogger(__name__)

app = Flask(__name__,
            template_folder='../templates',
            static_folder='../static')


@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('dashboard.html')


@app.route('/api/leads')
def get_leads():
    """API endpoint for recent leads."""
    leads = processing_history.get_recent(20)
    return jsonify([
        {
            "record_id": l.record_id,
            "name": l.name,
            "timestamp": l.timestamp.isoformat(),
            "tier": l.tier,
            "score": l.score,
            "status": l.status,
            "injury_type": l.injury_type,
            "county": l.county,
            "clio_matter_url": l.clio_matter_url,
            "error": l.error,
        }
        for l in leads
    ])


@app.route('/api/stats')
def get_stats():
    """API endpoint for processing statistics."""
    stats = processing_history.get_stats()
    stats["last_updated"] = datetime.now().isoformat()
    return jsonify(stats)


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})


def run_dashboard(host: str = "127.0.0.1", port: int = 8080):
    """Run the dashboard server."""
    logger.info(f"Starting dashboard on http://{host}:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    config = load_config()
    run_dashboard(config.dashboard_host, config.dashboard_port)
