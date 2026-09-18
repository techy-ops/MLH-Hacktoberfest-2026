# PayprAPI — Pay-Per-Request AI API Marketplace

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14.x-black.svg?style=flat&logo=next.js&logoColor=white)](https://nextjs.org/)
[![Node.js](https://img.shields.io/badge/Node.js-18%2B-339933.svg?style=flat&logo=node.js&logoColor=white)](https://nodejs.org/)
[![Algorand](https://img.shields.io/badge/Blockchain-Algorand%20Testnet-000000.svg?style=flat&logo=algorand&logoColor=white)](https://algorand.technologies)
[![Protocol](https://img.shields.io/badge/Protocol-X402%20(HTTP%20402)-7928CA.svg?style=flat)](https://github.com)
[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=flat)](LICENSE)

> A decentralized, pay-per-use AI API marketplace and agent execution engine powered by the **HTTP 402 Payment Required (X402) protocol** and the **Algorand blockchain**.

---

## 📑 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [X402 Protocol Flow](#-x402-protocol-flow)
- [Tech Stack](#-tech-stack)
- [Project Directory Structure](#-project-directory-structure)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
  - [1. Environment Configuration](#1-environment-configuration)
  - [2. Generate Wallets](#2-generate-wallets)
  - [3. Install Dependencies](#3-install-dependencies)
  - [4. Launch All Services](#4-launch-all-services)
- [AI Services Catalog](#-ai-services-catalog)
- [Developer & Agent Integration](#-developer--agent-integration)
  - [Autonomous 3-Step Handshake](#autonomous-3-step-handshake)
  - [cURL Walkthrough](#curl-walkthrough)
  - [Python Agent Example](#python-agent-example)
  - [Node.js / TypeScript Example](#nodejs--typescript-example)
- [Simulation Mode vs Live Testnet](#-simulation-mode-vs-live-testnet)
- [Automatic On-Chain Refunds](#-automatic-on-chain-refunds)
- [Environment Variables Reference](#-environment-variables-reference)
- [Testing & Verification](#-testing--verification)
- [Troubleshooting & FAQ](#-troubleshooting--faq)
- [License](#-license)

---

## 💡 Overview

Traditional SaaS API monetization models rely on monthly subscriptions, tiered enterprise contracts, and credit cards. This model creates major friction for modern software architecture:

1. **Autonomous AI Agents** cannot register credit cards or sign up for recurring monthly plans.
2. **Developers and Microservices** pay for idle subscriptions they rarely use.
3. **API Providers** face high payment processor fees, chargeback fraud, and complex billing infrastructure.

**PayprAPI** solves this by reviving the native web standard **`HTTP 402 Payment Required`**. API consumers (both human developers and autonomous AI agents) pay micro-amounts in ALGO per request directly on Algorand's fast, low-cost layer-1 network.

---

## ✨ Key Features

- **Standardized X402 Payment Negotiation**: Gateway responds with machine-readable `402 Payment Required` headers and JSON specifying recipient wallet, network, token currency, and exact price.
- **Autonomous Agent Console**: Dedicated agent pipeline simulation UI allowing AI agents to plan multi-step workflows (e.g., Translate → Sentiment Analysis → Summarization) with automated escrow payments.
- **Production-Grade AI Microservices**:
  - 🌐 **Neural Translation**: 50+ languages with auto-detection via `deep-translator`.
  - 📝 **Text Summarization**: Document and article summarization with sentence control.
  - 🎯 **Sentiment & Tone Analysis**: Polarity, subjectivity, and emotion breakdown scores.
  - 🎨 **Diffusion Image Generation**: Multi-style photorealistic, anime, cinematic, and digital art generation powered by Flux / Pollinations AI.
- **Automated On-Chain Refunds**: If an upstream AI service experiences an error or network drop after payment confirmation, the gateway automatically issues a refund transaction back to the payer's wallet.
- **Replay Attack & Double-Spend Defense**: In-memory hash caches and persistent database checks prevent re-use of past transaction IDs.
- **Zero-Friction Simulation Mode**: Test and develop locally without needing testnet tokens. Simulation mode accepts synthetic transaction IDs instantly.
- **Provider & Analytics Dashboards**: Real-time telemetry tracking request volume, revenue distribution, latency, and registered endpoints.

---

## 🏗️ System Architecture

```
                    ┌────────────────────────────────────────────────┐
                    │               Consumer Clients                 │
                    │   • Web App UI (:3000)   • Autonomous Agents   │
                    └───────────┬────────────────────────▲───────────┘
                                │                        │
         1. HTTP Request (No Tx)│        3. Resend with  │ 4. AI Response
                                │        X-Payment Header│
                                ▼                        │
                    ┌────────────────────────────────────┴───────────┐
                    │          PayprAPI Gateway (:8000)              │
                    │  • X402 Payment Interceptor                    │
                    │  • Algorand Payment Verifier                   │
                    │  • Replay Attack Defense                       │
                    │  • Auto-Refund Orchestrator                    │
                    └───────────┬────────────────────────▲───────────┘
                                │                        │
                 2. 402 Response│          Forward Valid │
                 (Payment Spec) │                Payment │
                                ▼                        │
      ┌─────────────────────────────┐         ┌──────────┴───────────────┐
      │  Algorand Testnet (AlgoNode)│         │ FastAPI AI Engine (:8001)│
      │  • Algod Node (:443)        │         │  • Translation Router    │
      │  • Indexer Service          │         │  • Summarization Router  │
      │  • ~3.3s Block Finality     │         │  • Sentiment Router      │
      └─────────────────────────────┘         │  • Image Gen (Flux)      │
                                              └──────────────────────────┘
```

---

## 💳 X402 Protocol Flow

```
Client / Agent                     PayprAPI Gateway                  Algorand Network / AI
      │                                    │                                    │
      │── 1. POST /api/translate ─────────>│                                    │
      │      (No payment headers)          │                                    │
      │                                    │                                    │
      │<── 2. HTTP 402 Payment Required ───│                                    │
      │      { amount: 0.001,              │                                    │
      │        recipient: "ADDR...",       │                                    │
      │        currency: "ALGO" }          │                                    │
      │                                    │                                    │
      │── 3. Broadcast Payment Tx ─────────────────────────────────────────────>│
      │<─── Returns Confirmed TxID ─────────────────────────────────────────────│
      │                                    │                                    │
      │── 4. POST /api/translate ─────────>│                                    │
      │      Header: X-Payment: txid:<ID>  │                                    │
      │                                    │── 5. Verify Tx (Amount, Receiver) >│
      │                                    │<── Verification Confirmed ─────────│
      │                                    │                                    │
      │                                    │── 6. Execute AI Service ──────────>│
      │                                    │<── Returns Inference Result ───────│
      │<── 7. HTTP 200 OK + AI Result ─────│                                    │
      │                                    │                                    │
      │      [If AI Service Fails]:        │                                    │
      │<── 8. HTTP 502/Error + Refund Tx ──│── Auto-issues refund transaction ─>│
```

---

## 💻 Tech Stack

| Layer | Technology | Description |
| :--- | :--- | :--- |
| **Frontend** | [Next.js 14](https://nextjs.org/), [React](https://react.dev/), [TypeScript](https://www.typescriptlang.org/) | Modern marketplace interface, developer explore playground, agent console |
| **Styling & Charts** | [Tailwind CSS](https://tailwindcss.com/), [Recharts](https://recharts.org/), Space Grotesk / Inter | High-performance dashboard visualizations and responsive design |
| **API Gateway** | [Node.js](https://nodejs.org/), [Express](https://expressjs.com/), [algosdk](https://github.com/algorand/js-algorand-sdk) | X402 protocol middleware, verification, proxying, and refund engine |
| **Database** | [Supabase](https://supabase.com/) / [PostgreSQL](https://www.postgresql.org/) | API registry persistence, transaction auditing, and provider stats |
| **AI Microservices** | [Python 3.9+](https://www.python.org/), [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/) | High-concurrency AI service execution engine with OpenAPI docs |
| **NLP & Translation** | [deep-translator](https://github.com/nidhaloff/deep-translator), [TextBlob](https://textblob.readthedocs.io/) | Multi-language translation, document summarization, sentiment classification |
| **Image Generation** | [Pollinations AI](https://pollinations.ai/) (Flux Model) | High-definition text-to-image synthesis across 6+ artistic styles |
| **Blockchain** | [Algorand Testnet](https://testnet.algoexplorer.io/) via [AlgoNode](https://algonode.io/) | Pure Proof-of-Stake micropayments with sub-penny fees and fast finality |

---

## 📂 Project Directory Structure

```text
PayprAPI/
├── .env.example               # Central environment variables template
├── .gitignore                 # Standard repository ignores
├── gen_wallet.py              # Python utility to create Algorand testnet accounts
├── run-marketplace.bat        # Windows batch script to launch all 3 tiers
├── start-all.ps1              # PowerShell script to launch all 3 tiers
├── README.md                  # Project documentation
│
├── backend/
│   ├── ai-services/           # FastAPI AI Services Application (Port 8001)
│   │   ├── main.py            # FastAPI entry point & route definitions
│   │   ├── requirements.txt   # Python package dependencies
│   │   ├── start.bat          # Service startup script
│   │   ├── models/            # Pydantic schemas for requests and responses
│   │   ├── middleware/        # Payment guard & authentication middleware
│   │   ├── services/          # Algorand helper and utility routines
│   │   └── routers/           # Individual service endpoints:
│   │       ├── translate.py   # 🌐 POST /api/translate
│   │       ├── summarize.py   # 📝 POST /api/summarize
│   │       ├── sentiment.py   # 🎯 POST /api/sentiment
│   │       └── image_gen.py   # 🎨 POST /api/image/generate
│   │
│   └── gateway/               # Node.js Express Gateway (Port 8000)
│       ├── server.js          # Express app, proxying & refund handlers
│       ├── package.json       # Gateway Node.js dependencies
│       ├── start.bat          # Gateway startup script
│       ├── gen-wallet.mjs     # JavaScript utility to generate test wallets
│       ├── test-flow.mjs      # CLI script verifying full agent payment cycle
│       ├── middleware/
│       │   └── x402.js        # Core HTTP 402 verification middleware
│       ├── lib/
│       │   ├── algorand.js    # Algorand testnet & simulation verification
│       │   ├── database.js    # Supabase connection & demo seed data
│       │   └── refund.js      # Automatic on-chain refund handler
│       └── routes/
│           ├── registry.js    # GET /registry (catalog & marketplace stats)
│           ├── facilitator.js # POST /facilitator/verify & fraud checks
│           ├── payment.js     # POST /payment/send (on-chain testnet signer)
│           ├── provider.js    # GET/POST /provider (developer accounts)
│           └── analytics.js   # GET /analytics (time-series activity data)
│
└── frontend/                  # Next.js 14 Web Application (Port 3000)
    ├── app/
    │   ├── layout.tsx         # Root layout with fonts & wallet state wrapper
    │   ├── page.tsx           # Marketplace home & landing hero
    │   ├── explore/           # Interactive API testing playground
    │   ├── dashboard/         # Provider dashboard & monetization metrics
    │   ├── analytics/         # Global network throughput & usage analytics
    │   ├── agent-console/     # Autonomous AI agent simulation studio
    │   └── components/        # Reusable UI cards, wallet connect modal, nav
    ├── package.json           # Frontend dependencies
    └── start.bat              # Frontend startup script
```

---

## ⚡ Prerequisites

Before getting started, make sure you have the following installed:

- **Python**: Version `3.9` or higher ([python.org](https://www.python.org/downloads/))
- **Node.js**: Version `18.x` or higher ([nodejs.org](https://nodejs.org/))
- **Package Managers**: `npm` and `pip`
- **Git**: Installed and configured on your system

---

## 🚀 Quick Start

### 1. Environment Configuration

Create your `.env` file from the provided template:

```bash
# In the root directory:
cp .env.example .env
```

If you are testing locally in **Simulation Mode**, the default settings in `.env.example` will work out of the box (`SIMULATION_MODE=true`).

### 2. Generate Wallets

If you plan to run real Algorand testnet transactions:

```bash
# Run the wallet generator
python gen_wallet.py
```

This will print an address and 25-word mnemonic phrase. Add them to your `.env`:
```env
PROVIDER_WALLET_ADDRESS=your_generated_address_here
PROVIDER_WALLET_MNEMONIC=your_twenty_five_word_mnemonic_here
```

To fund your testnet account with free test ALGO, visit the official [Algorand Testnet Dispenser](https://bank.testnet.algorand.network/).

### 3. Install Dependencies

Install dependencies for all three layers:

```bash
# 1. Install FastAPI AI dependencies
cd backend/ai-services
pip install -r requirements.txt

# 2. Install Gateway dependencies
cd ../gateway
npm install

# 3. Install Frontend dependencies
cd ../../frontend
npm install
```

### 4. Launch All Services

#### Option A: One-Click Startup (Recommended)

- **PowerShell (Windows)**:
  ```powershell
  .\start-all.ps1
  ```
- **Command Prompt (Windows)**:
  ```cmd
  run-marketplace.bat
  ```

#### Option B: Manual Multi-Terminal Startup

Open 3 separate terminals:

```bash
# Terminal 1 — AI Services (Port 8001)
cd backend/ai-services
python main.py

# Terminal 2 — Node.js Gateway (Port 8000)
cd backend/gateway
npm run dev

# Terminal 3 — Next.js Frontend (Port 3000)
cd frontend
npm run dev
```

#### Option C: Access Endpoints

Once booted, open your browser:
- 🌐 **Marketplace**: [http://localhost:3000](http://localhost:3000)
- 🔍 **Interactive Explorer**: [http://localhost:3000/explore](http://localhost:3000/explore)
- 🤖 **Agent Console**: [http://localhost:3000/agent-console](http://localhost:3000/agent-console)
- 📊 **Provider Dashboard**: [http://localhost:3000/dashboard](http://localhost:3000/dashboard)
- 📈 **Network Analytics**: [http://localhost:3000/analytics](http://localhost:3000/analytics)
- 📖 **FastAPI Swagger Docs**: [http://localhost:8001/docs](http://localhost:8001/docs)
- 🚪 **Gateway API Status**: [http://localhost:8000](http://localhost:8000)

---

## 🔌 AI Services Catalog

| Service | Endpoint | Method | Cost | Parameters | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Translation** | `/api/translate` | `POST` | `0.001 ALGO` | `text`, `source_lang`, `target_lang` | Translates text between 50+ languages with auto-detection. |
| **Summarization** | `/api/summarize` | `POST` | `0.002 ALGO` | `text`, `max_sentences` | Generates concise, cohesive summaries of long documents. |
| **Sentiment Analysis** | `/api/sentiment` | `POST` | `0.001 ALGO` | `text` | Classifies polarity, subjectivity, and granular emotion scores. |
| **Image Generation** | `/api/image/generate` | `POST` | `0.005 ALGO` | `prompt`, `style`, `width`, `height` | High-definition diffusion image generation (Flux model). |

---

## 🤖 Developer & Agent Integration

### Autonomous 3-Step Handshake

Every protected AI service follows the **X402 Specification**:

1. **Inquire**: Send request without payment headers.
2. **Challenge**: Gateway returns `402 Payment Required` containing price and recipient.
3. **Fulfill & Execute**: Submit payment to Algorand, attach transaction ID as `X-Payment: txid:<TX_ID>`, and receive the AI result.

---

### cURL Walkthrough

#### Step 1: Initial Request (Returns 402)
```bash
curl -i -X POST http://localhost:8000/api/summarize \
  -H "Content-Type: application/json" \
  -d '{"text": "The Algorand blockchain enables atomic micro-transactions."}'
```

**Response Header & Body:**
```http
HTTP/1.1 402 Payment Required
X-402-Version: 1
Content-Type: application/json

{
  "x402Version": 1,
  "error": "Payment Required",
  "accepts": [
    {
      "scheme": "algorand",
      "network": "testnet",
      "amount": "0.002",
      "currency": "ALGO",
      "recipient": "AQPT62NH6YGDDMUGSSYJYOVEDDNCR3LRV7SF37XA5LR5DRYFJBTY4P4Y3E",
      "memo": "/api/summarize:d94a12ec"
    }
  ],
  "instructions": {
    "step1": "Send 0.002 ALGO to recipient on Algorand testnet",
    "step2": "Get your transaction ID from the Algorand explorer",
    "step3": "Resend this request with header: X-Payment: txid:<YOUR_TX_ID>"
  }
}
```

#### Step 2: Resend with Payment Header (Returns 200)
```bash
curl -X POST http://localhost:8000/api/summarize \
  -H "Content-Type: application/json" \
  -H "X-Payment: txid:SIM_TX_9876543210" \
  -d '{"text": "The Algorand blockchain enables atomic micro-transactions."}'
```

**Response:**
```json
{
  "original_length": 58,
  "summary": "Algorand blockchain enables atomic micro-transactions.",
  "reduction": "15.5%",
  "service": "Summarization v1.0"
}
```

---

### Python Agent Example

```python
import requests

GATEWAY_URL = "http://localhost:8000/api/translate"
payload = {"text": "Hello, how are you?", "target_lang": "es"}

# 1. Initial attempt
response = requests.post(GATEWAY_URL, json=payload)

if response.status_code == 402:
    challenge = response.json()
    payment_spec = challenge["accepts"][0]
    print(f"[Agent] Payment Required: {payment_spec['amount']} ALGO to {payment_spec['recipient']}")

    # 2. In production: sign & broadcast Algorand transaction using py-algorand-sdk
    # In Simulation Mode: generate a synthetic ID (>=10 chars)
    tx_id = "SIM_TX_AGENT_PAYMENT_12345"

    # 3. Resend with X-Payment header
    headers = {"X-Payment": f"txid:{tx_id}"}
    paid_response = requests.post(GATEWAY_URL, json=payload, headers=headers)
    print("[Agent] Result:", paid_response.json())
```

---

### Node.js / TypeScript Example

```typescript
async function callPayprAPI(endpoint: string, body: object) {
  const url = `http://localhost:8000${endpoint}`;

  // 1. Initial call
  const initial = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (initial.status === 402) {
    const challenge = await initial.json();
    const { amount, recipient } = challenge.accepts[0];
    console.log(`[X402] Payment Required: ${amount} ALGO to ${recipient}`);

    // Generate or execute payment
    const txId = `SIM_${Date.now()}_${Math.random().toString(36).substring(7)}`;

    // Resend with verified header
    const finalResponse = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Payment': `txid:${txId}`,
      },
      body: JSON.stringify(body),
    });

    return await finalResponse.json();
  }

  return await initial.json();
}
```

---

## 🧪 Simulation Mode vs Live Testnet

PayprAPI includes a built-in switch between local simulation and real on-chain validation:

### Simulation Mode (`SIMULATION_MODE=true`)
- **Default for local development.**
- No wallet funding or testnet connectivity required.
- Any transaction ID string of **10 or more characters** is automatically validated.
- Prefixing a transaction ID with `FAIL` (e.g. `FAIL_TEST_123`) simulates a failed transaction to test client error recovery.
- Use the **"Auto-Generate TX ID"** button in the Explore tab or Agent Console for 1-click testing.

### Live Algorand Testnet (`SIMULATION_MODE=false`)
- Verifies real on-chain transaction records via the public AlgoNode Indexer (`https://testnet-idx.algonode.cloud`).
- Confirms receiver address matches `PROVIDER_WALLET_ADDRESS`.
- Validates the exact microALGO payment amount (`amount / 1,000,000`).
- Checks for block confirmation rounds and confirms payment transaction type.

---

## 🛡️ Automatic On-Chain Refunds

When an autonomous client pays for an API call, there is always a risk that the downstream AI service may fail, throw a timeout, or experience an out-of-memory error.

In PayprAPI:
1. When a client submits a valid payment header `X-Payment: txid:...`, the gateway notes the payer's address (`req.x402_sender`).
2. If the upstream FastAPI container returns a non-200 status code or a network error occurs:
   - The gateway invokes `issueRefund()` ([backend/gateway/lib/refund.js](file:///d:/PayprAPI/backend/gateway/lib/refund.js)).
   - A reverse transaction transfers the exact amount of ALGO back to the user's address.
   - The failed transaction record in the database is marked as `refunded` with the new `refund_tx_id`.
   - The client receives a clean error payload containing the refund transaction confirmation:
     ```json
     {
       "error": "AI Service Error",
       "refund_issued": true,
       "refund_tx_id": "REFUND_ALGO_TX_HASH..."
     }
     ```

---

## ⚙️ Environment Variables Reference

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `ALGORAND_NETWORK` | `testnet` | Algorand target network (`testnet`, `mainnet`) |
| `ALGORAND_ALGOD_URL` | `https://testnet-api.algonode.cloud` | Public Algod RPC node URL |
| `ALGORAND_INDEXER_URL` | `https://testnet-idx.algonode.cloud` | Public Algorand indexer URL |
| `PROVIDER_WALLET_ADDRESS` | — | Receiver wallet address for API payments |
| `PROVIDER_WALLET_MNEMONIC` | — | 25-word mnemonic used to issue on-chain refunds |
| `AI_SERVICE_PORT` | `8001` | Port for the FastAPI AI services backend |
| `AI_SERVICE_HOST` | `0.0.0.0` | Binding host for FastAPI |
| `INTERNAL_API_SECRET` | — | Shared internal communication secret |
| `GATEWAY_PORT` | `8000` | Port for the Express gateway server |
| `AI_SERVICES_URL` | `http://localhost:8001` | Gateway proxy destination for AI calls |
| `SIMULATION_MODE` | `true` | `true` for local mock validation; `false` for real blockchain |
| `SUPABASE_URL` | — | *(Optional)* Supabase PostgreSQL URL |
| `SUPABASE_SERVICE_ROLE_KEY` | — | *(Optional)* Supabase service key for DB operations |
| `NEXT_PUBLIC_GATEWAY_URL` | `http://localhost:8000` | Gateway endpoint used by Next.js frontend |
| `NEXT_PUBLIC_AI_SERVICES_URL` | `http://localhost:8001` | AI services direct URL for docs |

---

## 🧪 Testing & Verification

PayprAPI includes preconfigured test scripts to verify the end-to-end payment loop:

```bash
# Test the full 3-step agent payment flow in Node.js
cd backend/gateway
node test-flow.mjs
```

**Expected output:**
```text
--- Phase 5: Testing Agent-to-Agent Payment Flow ---
[Step 1] Requesting without payment...
✓ Received 402 Payment Required
  Recipient: AQPT62NH6YGDDMUGSSYJYOVEDDNCR3LRV7SF37XA5LR5DRYFJBTY4P4Y3E
  Amount: 0.002 ALGO

[Step 2] Simulating payment with TXID: SIM_TEST_k91b2
[Step 3] Resending request with X-Payment header...
✓ Received 200 OK
  AI Response Summary: The X402 protocol enables autonomous micro-transactions.

--- SUCCESS: Agent-to-Agent Payment Flow verified! ---
```

---

## ❓ Troubleshooting & FAQ

### 1. Port Conflicts (3000, 8000, or 8001 already in use)
- Ensure no lingering processes are running from previous sessions:
  ```powershell
  # Check ports on Windows
  Get-NetTCPConnection -LocalPort 3000, 8000, 8001 -ErrorAction SilentlyContinue
  ```
- Change `GATEWAY_PORT` or `AI_SERVICE_PORT` in your `.env` file if needed.

### 2. Algorand Indexer Delay (`Indexer delay` error)
- Algorand blocks finalize in ~3.3 seconds, but public indexer endpoints may take 1–3 seconds to index new transactions.
- The gateway includes an automatic 5-attempt retry loop with exponential backoff before reporting a transaction as not found.

### 3. "Insufficient Balance in Client Wallet"
- If testing on live testnet, ensure the client wallet has at least `0.1 ALGO` to cover the minimum balance requirement and transaction fee (`0.001 ALGO`).
- Fund your address at [bank.testnet.algorand.network](https://bank.testnet.algorand.network/).

### 4. Supabase Connection Warning
- If Supabase environment variables are omitted, the gateway gracefully operates in **offline fallback mode** using an in-memory registry, ensuring local development remains uninterrupted.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE). Feel free to adapt and build upon this platform for your own decentralized AI and micropayment architectures.
