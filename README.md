# Internship Project
SVM-accurate simulation tool for exploring arbitrage loops and oracle vulnerabilities on Solana using AI agents.

## Project Goal
Build a simulation tool that accurately models the *Solana Virtual Machine (SVM)* to:
- Explore *arbitrage loops* across Solana markets
- Identify and test *oracle vulnerabilities*
- Use *AI agents* to automate and analyze attack/trade strategies
- Implement in *Python* and *Rust*

## Roadmap
| Step | Task | Status |
| ----- | ----- | ----- |
| Step 0 | Create CHANGELOG.md on GitHub | ✅ Done |
| Step 1 | Find Solana markets (JTX preferred + alternatives) | ✅ Done |
| Step 2 | Choose one market to focus on | ✅ Done |
| Step 3 | Install Solana and Anchor on local machine | ✅ Done |
| Step 4 | Write LiteSVM simulation script | ✅ Done |

## Step 4 — LiteSVM Script Goals
The simulation script will:
- Create a wallet for user *Alice*
- Create a wallet for user *Bob*
- Initialize a market on the chosen Solana DEX
- Airdrop tokens to Alice and Bob
- Print initial token balances
- Execute trades for both users
- Print updated token balances

## Tech Stack
| Tool | Purpose |
| ----- | ----- |
| Python | Main scripting and AI agent logic |
| Rust | Low-level SVM simulation components |
| LiteSVM | Lightweight Solana VM simulator |
| Anchor | Solana smart contract framework |
| Solana CLI | Local validator and tooling |

## GitHub Workflow
- Branches follow type/short-description convention (e.g. feat/litesvm-script, docs/update-readme)
- Each PR is small, focused, and reviewed by the internship supervisor
- Issues are created for each task before work begins

## Author
[@Scorpion_Sign] — Solana Development Intern