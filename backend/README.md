# PathwaySA

PathwaySA is a mobile-first higher-education journey companion designed to help South African students discover suitable study pathways, explore funding opportunities, track applications, and access AI-assisted guidance throughout their journey into higher education.

The system combines a Flutter mobile application with a FastAPI backend and uses structured programme and bursary data to provide personalised recommendations.

## Project Goals

PathwaySA aims to support students across the higher-education journey by providing:

- Study programme discovery
- Programme eligibility checking
- Personalised programme recommendations
- University and campus filtering
- Bursary and funding discovery
- Application tracking
- Saved study opportunities
- Multilingual AI assistance
- Student profile management
- Academic and higher-education guidance

## Current Architecture

```text
Flutter Mobile App
        ↓
FastAPI Backend
        ↓
Programme Services / Bursary Services
        ↓
SQLite Databases
        ↓
AI Assistant
