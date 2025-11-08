# BEST FARM - Telegram Bot

## Overview
BEST FARM is a Telegram farming game bot built with Python and aiogram. Users can purchase virtual animals, earn daily income, manage their balance, and invite friends through a referral system.

## Project Structure
- `main.py` - Main bot application with all game logic, handlers, and database management
- `keep_alive.py` - Flask server for keeping the bot alive (optional, not currently used)
- `requirements.txt` - Python dependencies
- `farm_bot.db` - SQLite database (auto-created)

## Features
- **Animal System**: Users can buy different animals (chickens, ducks, rabbits) that generate daily income
- **Economy**: Balance system with deposits and withdrawals via Payeer
- **Referral System**: Users can invite friends and earn referrals
- **Admin Panel**: Admin commands for managing users, balances, and transactions
- **Automated Income**: Daily automated income collection at midnight (Tashkent timezone)
- **Persistence**: SQLite database stores users, animals, and transactions

## Technical Details
### Database Schema
- `users`: user_id, username, balance, referrals, ref_by
- `animals`: user_id, animal_type, amount, purchased_at
- `transactions`: id, user_id, description, amount, timestamp

### Environment Variables
- `BOT_TOKEN` (required): Telegram bot token from @BotFather
- `ADMIN_ID` (required): Telegram user ID of the admin
- `PAYEER_ACCOUNT` (optional): Payeer account for payments (default: P1062588236)
- `BOT_USERNAME` (optional): Bot username (default: bestfarlm_bot)
- `ADMIN_USERNAME` (optional): Admin username (default: mominjon_gofurov)
- `BOT_NAME` (optional): Bot display name (default: BEST FARM 🌱)

## Setup Instructions
1. Set up required secrets in Replit Secrets:
   - `BOT_TOKEN`: Get from @BotFather on Telegram
   - `ADMIN_ID`: Your Telegram user ID (get from @userinfobot)

2. The bot will automatically start when you run the project

3. Optional: Configure payment details by setting `PAYEER_ACCOUNT` environment variable

## Recent Changes (2025-11-08)
- Migrated hardcoded secrets to environment variables for security
- Fixed syntax error in payment processing function (indentation issue)
- Updated Flask server to use port 5000 instead of 8080
- Added .gitignore for Python project
- Configured Telegram Bot workflow for console output

## User Preferences
- Language: Uzbek (O'zbek)
- Payment system: Payeer
- Timezone: Asia/Tashkent (UTC+5)

## Architecture Notes
- Async architecture using asyncio and aiogram 3.x
- SQLite for data persistence
- APScheduler for daily automated income collection (runs at midnight Tashkent time)
- FSM (Finite State Machine) for multi-step user interactions
- Inline and reply keyboard markups for user interface
