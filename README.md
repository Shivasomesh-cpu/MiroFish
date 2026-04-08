<div align="center">

<img src="./static/image/Posiedon_logo_compressed.jpeg" alt="Posiedon Logo" width="75%"/>

<em>A Simple and Universal Swarm Intelligence Engine for Forecasting Complex Outcomes</em>

</div>

## Overview

Posiedon is a multi-agent prediction and simulation platform. It turns source documents and seed inputs into a structured social world, generates agent personas, runs large-scale simulations, and produces reports plus interactive follow-up analysis.

## Core Workflow

1. Graph building from uploaded source material
2. Environment and persona generation
3. Dual-platform simulation
4. Report generation
5. Interactive analysis with simulated agents

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.11
- `uv`

### Setup

```bash
cp .env.example .env
npm run setup:all
```

### Run

```bash
npm run dev
```

The frontend runs on port `3000` and the backend runs on port `5001` by default.

## Required Environment Variables

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus
ZEP_API_KEY=your_zep_api_key
```

## Windows

```powershell
git clone https://github.com/Shivasomesh-cpu/posiedon.git
cd posiedon
copy .env.example .env
npm run setup:all
npm run dev
```

## Notes

- The product branding in this repository is `Posiedon`.
- The upstream GitHub repository uses the `posiedon` repository name.

## Contact

For collaboration or recruiting inquiries: `posiedon@shanda.com`
