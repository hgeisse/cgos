# CGOS System Analysis - Complete Documentation Index

This directory contains comprehensive documentation of the CGOS (Computer Go Server) client-server system architecture and implementation.

## Documents Included

### 1. CGOS_SYSTEM_ANALYSIS.md (888 lines, 28KB)
**Comprehensive technical analysis covering all aspects of the system**

Sections:
1. **Project Structure** - Complete directory tree with file descriptions
   - Server components (cgos/, app/, gogame/, util/)
   - Client components (src/, configs/, doc/)
   - Configuration and documentation

2. **Server Implementation** - Core server components and architecture
   - Entry point (server.py, runServer())
   - Main event loop (server_main(), asyncio)
   - Client handler (Client class, readTask, writeTask)
   - Message handlers (player, viewer, admin)
   - Global state management (act, games, gme, db)

3. **Client Implementation** - Engine integration and communication
   - Entry point (cgosclient.py)
   - Connection management
   - Main loops (mainloop, _handlerloop)
   - Message handlers (8 handlers: protocol, username, password, setup, play, genmove, gameover, info)
   - GTP engine integration (EngineConnector, AnalyzeResultParser)

4. **Communication Mechanism** - Protocol specification
   - Protocol overview (text-based, line-delimited, UTF-8)
   - Client-server message flow (with diagram)
   - Message types table (server→client, client→server)
   - Server-side routing (player_respond state machine)

5. **Key Data Structures** - Game representation and storage
   - Game class definition
   - Database schema (5 tables in state.db, 1 in archive.db)
   - Setup message format
   - Move message format
   - Game result formats
   - SGF record generation

6. **Main Workflows** - System-level processes
   - Client connection workflow (8 steps)
   - Server game scheduling workflow
   - Game execution flow (move exchange, validation, end detection)
   - Rating update workflow (Elo system)

7. **Technologies & Frameworks** - Technology stack
   - Server-side: Python 3.12, asyncio, sqlite3, Jinja2, passlib, PyYAML
   - Client-side: Python 3.x, socket, subprocess, logging, PyYAML
   - Protocols: GTP, SGF, Elo rating system
   - Configuration management

8. **Concurrency Model** - Threading and async patterns
   - Server concurrency (asyncio tasks, per-client I/O)
   - Scheduler task (periodic game management)
   - Client concurrency (single-threaded blocking I/O)
   - Subprocess management (GTP engine)

9. **Configuration Files** - Server and client settings
   - Server configuration (YAML template with all parameters)
   - Client configuration (YAML template with examples)
   - Board sizes (9x9, 13x13, 19x19)
   - Rating parameters (defaultRating, minK, maxK)

10. **File Paths Summary** - All critical file locations
    - Server core files (5 files)
    - Server game logic (2 files)
    - Client core files (4 files)
    - Configuration files (5 files)

---

### 2. CGOS_QUICK_REFERENCE.md (351 lines, 9.5KB)
**Quick reference guide for rapid lookup and debugging**

Sections:
1. System Overview - High-level architecture
2. Architecture Components - Server and client component trees
3. Message Flow Example - Step-by-step message sequence with examples
4. Key Files Table - 7 critical files with line counts and purposes
5. Critical Functions - 6 server + 6 client key functions
6. State Machine - Complete state machine diagram for server handler
7. Database Tables - state.db and archive.db schema
8. Message Types Summary - Commands, parameters, purposes
9. Configuration - Server and client YAML templates
10. Time Management - Milliseconds, increments, examples
11. Rating System - Elo formula and K-factor adjustment
12. Game Result Formats - Result string examples
13. Error Codes - Go move validation error codes
14. File Operations - Kill files, SGF, web data
15. Implementation Details - Blocking points, shutdown, matching, recovery
16. Performance Notes - Concurrent games, database, network, GTP
17. Common Issues & Debugging - 3 common issues with solutions
18. Links to Source - Document locations

---

## Quick Start Guide

### For Understanding the Architecture
1. Start with "Architecture Components" in QUICK_REFERENCE.md
2. Read "Project Structure" in SYSTEM_ANALYSIS.md
3. Review "Message Flow Example" in QUICK_REFERENCE.md

### For Implementing Changes
1. Identify the component (server/client/protocol)
2. Find relevant section in SYSTEM_ANALYSIS.md
3. Look up functions in QUICK_REFERENCE.md "Critical Functions"
4. Check file paths in SYSTEM_ANALYSIS.md section 10

### For Debugging Issues
1. Check "Common Issues & Debugging" in QUICK_REFERENCE.md
2. Consult "State Machine" diagram in QUICK_REFERENCE.md
3. Review relevant message handler in SYSTEM_ANALYSIS.md section 2 or 3

### For Adding Features
1. Understand current message protocol (section 4, SYSTEM_ANALYSIS.md)
2. Design new message types
3. Implement server handler (see _handle_player_* examples)
4. Implement client handler (see _handle_* examples)
5. Update both state machines accordingly

---

## Key File Locations

### Absolute Paths
- Analysis Document: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/CGOS_SYSTEM_ANALYSIS.md`
- Quick Reference: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/CGOS_QUICK_REFERENCE.md`
- This Index: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/ANALYSIS_INDEX.md`

### Server Source Code
- Main Server: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/cgos/app/cgos.py`
- Client Handler: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/cgos/app/client.py`
- Configuration: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/cgos/app/config.py`
- Rating: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/cgos/app/rating.py`
- Go Logic: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/cgos/gogame/go.py`
- Game State: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/cgos/gogame/game.py`

### Client Source Code
- Main Client: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/client/src/cgosclient.py`
- GTP Engine: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/client/src/gtpengine.py`
- SGF Handling: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/client/src/sgf.py`
- Configuration: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/client/src/config.py`

### Configuration Files
- Server 19x19: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/configs/generic/cgos19.yaml`
- Server 13x13: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/configs/generic/cgos13.yaml`
- Server 9x9: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/configs/generic/cgos9.yaml`
- Client Simple: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/client/configs/generic/simple.yaml`
- Client Full: `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/client/configs/generic/client.yaml`

---

## Analysis Methodology

The analysis was performed through:

1. **Directory Structure Exploration** - Complete file tree mapping
2. **Source Code Review** - Line-by-line examination of key files
3. **Function Identification** - Entry points, handlers, utilities
4. **Data Flow Analysis** - Message sequences, state transitions
5. **Protocol Specification** - Message formats, handshakes
6. **Database Schema Extraction** - Table structures, relationships
7. **Architecture Mapping** - Component interactions, dependencies
8. **Documentation Synthesis** - Comprehensive and quick-reference formats

---

## Document Statistics

| Aspect | Count |
|--------|-------|
| Total Lines of Documentation | 1,239 |
| System Analysis Sections | 10 |
| Quick Reference Sections | 20 |
| Server Components Documented | 5+ |
| Client Components Documented | 4+ |
| Message Types Identified | 10+ |
| Database Tables Described | 6 |
| Critical Functions Listed | 12 |
| Code Files Referenced | 25+ |
| Configuration Parameters | 20+ |

---

## Version Information

- **Analysis Date:** June 20, 2026
- **Project Location:** `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos`
- **Python Version:** 3.12.0 (server), 3.x (client)
- **Documentation Format:** Markdown

---

## Related Documentation

- **In-project docs:** `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/doc/doc.txt`
- **Server README:** `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/server/README`
- **Client README:** `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/client/README`
- **Main README:** `/home/hellwig/Go-Server/cgos-hg/try-ai/cgos/README`

---

## How to Use This Documentation

### For New Developers
1. Read SYSTEM_ANALYSIS.md sections 1-3 (structure and architecture)
2. Review QUICK_REFERENCE.md "Architecture Components" and "Message Flow Example"
3. Study the state machine diagram
4. Review specific handlers for the code area you'll work on

### For Integrations
1. Review section 4 "Communication Mechanism" in SYSTEM_ANALYSIS.md
2. Check QUICK_REFERENCE.md "Message Types Summary"
3. Implement according to message protocol specifications

### For Deployment
1. Review QUICK_REFERENCE.md "Configuration" section
2. Check SYSTEM_ANALYSIS.md section 9 for all config parameters
3. Refer to server/client README files for step-by-step setup

### For Maintenance
1. Use QUICK_REFERENCE.md for rapid reference
2. Consult SYSTEM_ANALYSIS.md for detailed implementation details
3. Check Critical Functions section for key entry points

---

## Questions Answered by This Documentation

- **What is CGOS?** System Overview in QUICK_REFERENCE.md
- **How are clients and servers connected?** Communication Mechanism (SYSTEM_ANALYSIS.md section 4)
- **What messages are exchanged?** Message Types Summary (QUICK_REFERENCE.md)
- **How does game scheduling work?** Main Workflows (SYSTEM_ANALYSIS.md section 6)
- **Where is the main logic?** File Paths Summary (SYSTEM_ANALYSIS.md section 10)
- **What are the state machines?** State Machine (QUICK_REFERENCE.md)
- **How are games rated?** Rating System (QUICK_REFERENCE.md and SYSTEM_ANALYSIS.md section 6.4)
- **What technologies are used?** Technologies & Frameworks (SYSTEM_ANALYSIS.md section 7)
- **How does concurrency work?** Concurrency Model (SYSTEM_ANALYSIS.md section 8)
- **What are common issues?** Common Issues & Debugging (QUICK_REFERENCE.md)

---

**Last Updated:** June 20, 2026  
**Status:** Complete and Comprehensive  
**Accuracy:** Cross-referenced with source code
