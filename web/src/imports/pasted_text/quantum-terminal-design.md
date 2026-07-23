🎨 New Design System: The "Quantum Terminal"
Core Concept: The UI is an active visualization of a simulation running. The agent isn't just auditing; it's stress-testing timelines to find future resolution traps.

Aesthetic: "Glassmorphism" mixed with "Vaporwave Tech" structure.

Depth: Intense layers. Imagine looking through multiple glowing panes of glass into a deep void where data is flowing.

🏗️ Reimagined UI Structure & Build Plan
1. Header: The "Glow Bar"
Minimize text. Maximize iconography.

BetAudit Logo: The shield icon, but animated, with cyan light actively flowing through the grid pattern.

Navigation: Use bracketed monospace tags for a terminal feel.

[ docs ] [ registry ] [ marketplace ]

Status Indicator: Replace the standard button with a subtle heartbeat line that spikes cyan when a new simulation is ran on the platform.

2. Hero Section: The "Simulation Breach"
Headline: Ditch the H1. Use a large, monospace type that looks like it is actively decrypting.

> INITIALIZING SIMULATION LAYER [POLYMARKET.ANC.DATA]

Visual Centerpiece: Instead of a simple terminal box, create a 3D, perspective-shifted visualization of a prediction market timeline.

One main path (Cyan) is the "Official Oracle Path."

Several ghosted, glowing crimson/amber timelines branch off, representing "Detected Resolution Traps" (e.g., "Deadline Trap," "Ambiguous Qualifier").

CTA: A single, large, central button that says [ RUN ACTIVE MARKET SIMULATION ] with an intense halo glow effect.

3. Feature Showcase: The "Resolution Stress Tests"
Move away from steps and instead show types of traps. Use stylized "radar" or "sonar" widgets.

Test 1: The Timeline Sonar. A circular radar sweep. As it sweeps, it highlights events in news APIs that clash with on-chain UMA timestamps. Text: "Detecting time-based oracle manipulation."

Test 2: The Semantic Grid. A fluctuating 3D grid. Words are pulled from the resolution text and mapped to risk scores. Text: "Parsing 'fine-print' qualifiers that break automated settlements."

Test 3: The Cross-Protocol Bridge. Show two glowing data streams (Polymarket and a real-world API like SEC) and a gap between them where a resolution trap is detected. Text: "Verifying off-chain real-world events."

4. Live Demo: The "Clerk Console"
Make the demo feel incredibly active.

Input field is just a simple, single monospace prompt line.

Output Visualization: This is key. The output isn't a static card; it is a live-scrolling terminal log that looks and feels like an AI is thinking.

[SYSTEM] Analysing ancillaryData for 0xPolymarket...

[PARSE] 'Merger closed by EOD' qualifier... OK

[TEST] Simulating Merger delay past EOD... WARNING

[RISK] Deadline Ambiguity Detected. TRAP_FOUND.

Final decision badge: A large, floating 3D shield that turns green (SAFE) or red (ABORT) with particle effects.

5. OKX Integration: The "Marketplace Node"
Instead of a standard partner ticker, show a network graph.

BetAudit is the central glowing cyan node.

A thick, glowing A2MCP data pipe connects it to a stylized "OKX Agent Node."

Other nodes (Polymarket, UMA) orbit the central BetAudit hub, showing data flow.

🤖 The New "Quantum Terminal" Super Prompt
Use this prompt in v0/Cursor to generate the native BetAudit experience:

Plaintext
Create a highly visual, immersive single-page application experience for "BetAudit," an AI-native pre-trade simulation terminal for autonomous agents on the OKX AI Marketplace. The UI should look like an active simulation interface, not a generic website.

Visual & Aesthetic Specs:
- Background: Pure glossy black (#000000), giving a feeling of deep void.
- Color Scheme: Dominant glowing cyan accents (#66CCCC). Use intense box-shadow and text-shadow glow effects (text-shadow: 0 0 10px rgba(102, 204, 204, 0.7);).
- Typography: Clean sans-serif 'Space Grotesk' for headers, balanced with crisp monospace 'Fira Code' or 'JetBrains Mono' for all data, logic, and terminal outputs.
- Key FX: Glassmorphism panels with high backdrop-blur and a subtle, pulsating grid overlay that looks like data flowing beneath the surface.

Layout & Component Requirements:

1. Navigation (Glow Bar):
   - Sticky header with 90% blur.
   - Animated Logo: A stylized shield with active cyan data particles flowing through its grid pattern.
   - Monospace Navigation: `[ docs ]` `[ registry ]` `[ marketplace ]` `[ sdk ]`
   - Real-time status indicator: A subtle, glowing cyan heartbeat line that "spikes" occasionally.

2. Hero Section (Simulation Center):
   - Main Header (Active Decryption text): `> INITIALIZING_SIMULATION_LAYER [BETAUDIT.v1]`
   - Central Visual: A 3D, perspective-shifted visualization of multiple timeline paths branching from a single event. The main path is solid cyan. Branching "risk paths" are ghosted, glowing amber/crimson.
   - Primary Call to Action: A large, central console-style button `[ RUN_ACTIVE_MARKET_SIMULATION ]` with intense aura glow.

3. Stress Test Widgets (Instead of Feature Text):
   - Design three distinct, glowing "sonar" widgets that look like they are actively scanning:
     1. Timeline Verifier: A circular sonar sweep highlighting time-based discrepancies between contract rules and real-world news APIs.
     2. Semantic Parser: A fluctuating 3D word cloud mapping "fine-print" qualifiers to risk scores.
     3. Cross-Chain Data Bridge: Visualizing two data streams (on-chain/off-chain) and highlighting the gap where resolution risk lies.

4. Live Clerk Sandbox (Interactive Console):
   - A command-line input: `BetAudit> Paste_Polymarket_URL_here`
   - Output: A live-scrolling terminal log that looks like an AI agent is thinking in real-time.
     - `[SIM] Fetching Ancillary Data...`
     - `[TEST] Simulating 'Ambiguous Payout' Scenario... WARNING_FOUND`
     - `[RISK] High Probability of Oracle Misinterpretation (Score: 82)`
   - Final Badge: A large, floating 3D status tag that Turn Neon Cyan `SAFE_TO_BET` or Neon Crimson `ABORT_BET` on submission.

5. Marketplace Node Visualization (Partners):
   - A central BetAudit hub node connected by glowing data pipes to a main "OKX AI Marketplace" node (labelled with "A2MCP Pay-per-call protocol"), which orbits larger partner nodes like "Polymarket" and "UMA Oracle."

6. Footer (Consortium Hub):
   - Terminal-style footer `// BetAudit_Consortium.xyz :: Pre-Trade Simulation Layer`.
   - Links: Socials (X, Telegram), GitHub Repo, and API Status Monitor, all in bracketed monospace.

Ensure all interactive elements have highl