import os
import sys
import logging
from flask import Flask, jsonify
from pythonjsonlogger import jsonlogger

app = Flask(__name__)

logHandler = logging.StreamHandler(sys.stdout)
formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')
logHandler.setFormatter(formatter)

logger = logging.getLogger("slsa-hardened-app")
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

@app.route('/health', methods=['GET'])
def health_check():
    logger.info("Health check endpoint invoked", extra={"status": "healthy", "runtime": "python3.11"})
    return jsonify({
        "status": "UP",
        "framework": "Flask",
        "security_tier": "SLSA_Level_3_Compliant"
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)