# CryptoSignalTracker - High-Level Codebase Analysis

## Executive Summary

CryptoSignalTracker is a sophisticated dual-engine cryptocurrency trading signal platform designed for automated market analysis and real-time signal generation. The system leverages Google Cloud Platform (GCP) services and provides trading signals through a Telegram bot interface.

## System Architecture Overview

The platform consists of two main trading engines:

### 1. MACRO Engine (Swing Trading)
- **Purpose**: Identifies longer-term swing trading opportunities
- **Time Frame**: 5-minute candle data
- **Deployment**: Google Cloud Function (`run-signal-generation`)
- **Data Source**: Kraken API
- **Output**: Directional bias (LONG/SHORT) and confidence scores

### 2. MICRO-SCALP Engine (High-Frequency Trading)
- **Purpose**: Captures short-term scalping opportunities
- **Time Frame**: 1-minute candle data  
- **Deployment**: Multiple Cloud Run services
- **Data Source**: Bybit WebSocket API
- **Strategy**: V5.2 "Champion" - RSI divergence + volume spike detection

## Core Components

### Data Pipeline
1. **Data Ingestion** (`micro_scalp_engine/data_ingestion.py`)
   - Connects to Bybit WebSocket for real-time trade data
   - Publishes raw data to `raw-tick-data-bybit` Pub/Sub topic
   - Monitors 9 cryptocurrency pairs (BTC, SOL, ETH, XRP, DOGE, SEI, LINK, SUI, ADA)

2. **Data Processing** (`micro_scalp_engine/data_processor.py`)
   - Aggregates raw trades into 1-minute OHLCV candles
   - Stores processed data in Bigtable (`market-data-1m` table)

3. **Logic Engine** (`micro_scalp_engine/logic_engine.py`)
   - Runs analysis every 15 seconds
   - Applies trading strategy (RSI + volume analysis)
   - Integrates macro bias for trade filtering
   - Publishes signals to `trade-signals-micro` topic

4. **Notification System** (`micro_scalp_engine/async_telegram_notifier/`)
   - Subscribes to trade signals
   - Sends formatted alerts to Telegram
   - Provides interactive chart generation
   - Uses Redis for message state management

### Supporting Services

- **Position Management**: Tracks open positions and prevents conflicting trades
- **Risk Management**: Calculates position sizes and stop-loss/take-profit levels
- **Macro Integration**: Aligns micro signals with macro market trends
- **Chart Generation**: Creates visual representations of trading opportunities

### Analysis Tools
- Multiple backtesting frameworks
- Pattern recognition and analysis
- Market move analyzers
- Performance evaluation scripts

## Technology Stack

### Core Technologies
- **Language**: Python 3.9/3.11
- **Cloud Provider**: Google Cloud Platform (GCP)

### GCP Services
- **Cloud Run**: Containerized microservices
- **Cloud Functions**: Serverless MACRO engine
- **Pub/Sub**: Event-driven messaging backbone
- **Bigtable**: High-performance time-series data storage
- **Firestore**: Position and configuration storage
- **Secret Manager**: Secure credential storage
- **Cloud Build**: CI/CD pipeline
- **Artifact Registry**: Container image storage

### External APIs
- **Bybit**: Real-time market data (WebSocket)
- **Kraken**: Market data for MACRO engine
- **Telegram Bot API**: User notifications
- **Google Gemini**: AI-powered market analysis
- **CryptoCompare**: Backup data source

### Libraries & Frameworks
- **pandas-ta**: Technical analysis
- **mplfinance**: Chart generation
- **pybit**: Bybit API client
- **python-telegram-bot**: Telegram integration
- **Firebase Admin SDK**: Firestore management

## Current Deployment Status

### Issues Identified
1. **Cloud Function Deployment Failure**
   - Error: Container failed to start on PORT=8080
   - Revision: `run-signal-generation-00072-hjb`
   - Root cause: Port misconfiguration in Dockerfile

2. **Local Development Setup**
   - Hard-coded paths in `start_services.sh`
   - Exposed API credentials in scripts

### Working Components
- Cloud Build pipeline configured
- Docker images building successfully
- Artifact Registry integration working
- Basic Flask web interface available

## Deployment Recommendations for Google Cloud

### 1. Immediate Fixes

#### Fix Cloud Function Port Issue
```dockerfile
# Update Dockerfile to expose correct port
EXPOSE 8080
ENV PORT=8080

# Ensure functions-framework uses PORT env var
CMD ["functions-framework", "--target", "run_signal_generation", "--source", "main.py", "--port", "${PORT:-8080}"]
```

#### Secure Credentials
- Remove hardcoded credentials from `start_services.sh`
- Use Secret Manager for all sensitive data
- Update local development to use service account authentication

### 2. Simplified Deployment Approach

#### Option A: Cloud Run Only (Recommended)
Convert the Cloud Function to a Cloud Run service for consistency:
1. Containerize the MACRO engine with proper HTTP server
2. Deploy all services as Cloud Run instances
3. Use Cloud Scheduler to trigger the MACRO engine
4. Benefits: Unified deployment model, better debugging, easier scaling

#### Option B: Hybrid Approach
Keep current architecture but fix configuration:
1. Fix the Cloud Function port binding
2. Ensure proper health checks
3. Use Cloud Build triggers for automated deployment
4. Set up proper monitoring and alerting

### 3. Infrastructure as Code

Create Terraform or Cloud Deployment Manager templates:
```yaml
# Example Cloud Run service definition
- name: micro-scalp-data-ingestion
  type: cloud-run-service
  properties:
    image: gcr.io/PROJECT_ID/data-ingestion:latest
    env:
      - name: GCP_PROJECT_ID
        value: telegram-signals-205cc
    minInstances: 1
    maxInstances: 10
```

### 4. Deployment Pipeline

```bash
# deployment.sh
#!/bin/bash
PROJECT_ID="telegram-signals-205cc"
REGION="us-central1"

# Build and deploy services
gcloud builds submit --config cloudbuild-services.yaml
gcloud run deploy micro-scalp-engine --source . --region $REGION
```

### 5. Monitoring & Operations

1. **Set up Cloud Monitoring dashboards**
   - Service health metrics
   - Trading signal frequency
   - API rate limits
   - Error rates

2. **Configure alerting policies**
   - Service downtime
   - Failed trades
   - API quota warnings

3. **Implement proper logging**
   - Structured logging with severity levels
   - Log aggregation for analysis
   - Retention policies

### 6. Cost Optimization

1. **Use appropriate machine types**
   - Cloud Run: CPU-optimized for compute-intensive tasks
   - Minimum instances only for critical services

2. **Implement proper autoscaling**
   - Scale based on Pub/Sub queue depth
   - Time-based scaling for market hours

3. **Optimize Bigtable usage**
   - Implement data retention policies
   - Use appropriate node configuration

## Next Steps

1. **Fix immediate deployment blockers**
   - Resolve Cloud Function port issue
   - Secure exposed credentials

2. **Standardize deployment**
   - Create unified deployment scripts
   - Document deployment procedures

3. **Implement monitoring**
   - Set up dashboards and alerts
   - Create runbooks for common issues

4. **Optimize for production**
   - Performance testing
   - Cost analysis and optimization
   - Security audit

## Conclusion

CryptoSignalTracker is a well-architected system with sophisticated trading logic and modern cloud-native design. The main deployment challenges are configuration-related and can be resolved with the recommended fixes. The easiest deployment path is to standardize on Cloud Run for all services, providing consistency and easier management. 