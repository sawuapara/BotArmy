# LangGraph Session Orchestrator

A local work prioritization system for MecanoLabs/MecanoConsulting. Uses LangGraph for workflow orchestration with a React + Tailwind dashboard.

## Architecture

```
┌─────────────────────────────────┐
│  React + Tailwind (Frontend)   │  Port 3000
│  - Dashboard UI                │
│  - Drag-drop queues            │
│  - Real-time updates           │
└─────────────────────────────────┘
              │ HTTP / WebSocket
              ▼
┌─────────────────────────────────┐
│  FastAPI (Backend)             │  Port 8000
│  - REST endpoints              │
│  - WebSocket for live updates  │
│  - Hosts LangGraph graphs      │
└─────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│  LangGraph                      │
│  - Session Orchestrator graph   │
│  - Ticket Worker graphs         │
│  - Checkpoints in SQLite        │
└─────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- npm or pnpm

### Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Copy .env.example to .env and fill in your API keys
# (Already done if you ran setup)

# Start the server
uvicorn src.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Open http://localhost:3000 in your browser.

## How It Works

### Session Orchestrator Flow

1. **Check Revenue** - Fetches hours from Harvest, compares to monthly target
2. **Determine Work Type** - If below target → Consulting, else → Product
3. **Fetch Tickets** - Gets tickets from JIRA (Consulting) or Salesforce (Product)
4. **Rank Tickets** - Scores based on client priority, age, urgency, completion %
5. **Select Ticket** - Picks top-ranked ticket
6. **Launch Worker** - Starts ticket-type-specific workflow
7. **Monitor Worker** - Tracks progress until complete or blocked

### Ticket Scoring Formula

```
score = client_weight
      + (estimated_hours * 10)
      + (completion_pct * 0.5)
      + (age_days * 0.5)
      + (urgent ? 100 : 0)
      + (blocker ? 75 : 0)
```

### Configuration

Edit `config/priorities.yaml` to customize:
- Client weights (Moloco, Fivesky, etc.)
- Project priorities (AdminPro, RadNexus, etc.)
- Scoring weights

Edit `config/targets.yaml` for:
- Monthly revenue target hours
- Billable projects list

## Development

### Project Structure

```
langgraph-orchestrator/
├── backend/
│   ├── src/
│   │   ├── api/           # REST endpoints (future)
│   │   ├── orchestrator/  # LangGraph graphs
│   │   │   ├── graph.py   # Main orchestrator graph
│   │   │   ├── state.py   # State schema
│   │   │   └── nodes/     # Individual nodes
│   │   ├── workers/       # Ticket type workflows
│   │   ├── tools/         # JIRA, Harvest, SF clients
│   │   └── main.py        # FastAPI app
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── hooks/         # Custom hooks (WebSocket)
│   │   └── types/         # TypeScript types
│   └── package.json
└── config/                # Shared config
```

## Roadmap

- [ ] Complete worker sub-graphs (bug, feature, question workflows)
- [ ] Salesforce/AdminPro ticket integration
- [ ] Interrupt and resume functionality
- [ ] Project queue (for non-consulting work)
- [ ] Time tracking integration (auto-log to Harvest)
- [ ] Port to AdminPro as native Salesforce feature

## Related

- [AdminPro Agent Orchestration Architecture](../../../MecanoLabs/Products/AdminPro/docs/AGENT-ORCHESTRATION-ARCHITECTURE.md) - Native Salesforce implementation plan
