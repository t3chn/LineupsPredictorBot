import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.models import DatabaseManager
from analyzers.lineup_predictor import LineupPredictor
from fetchers.logo_scraper import LogoScraper
from config import LEAGUES

logger = logging.getLogger(__name__)

class BotHandlers:
    def __init__(self, db_manager):
        self.db = db_manager
        self.predictor = LineupPredictor(db_manager)
        self.logo_scraper = LogoScraper()
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            user_id = update.effective_user.id
            logger.info(f"Start command called by user {user_id}")
            
            keyboard = []
            for league_key, league_info in LEAGUES.items():
                keyboard.append([InlineKeyboardButton(
                    f"{league_info['emoji']} {league_info['name']}", 
                    callback_data=f"league_{league_key}"
                )])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            welcome_message = (
                "⚽ Welcome to Fantasy Football Lineup Predictor!\n\n"
                "I can predict the most likely starting lineups for upcoming matches "
                "based on tactical formations, injury news, player form, and expert commentary.\n\n"
                "Please select a league to get started:"
            )
            
            await update.message.reply_text(welcome_message, reply_markup=reply_markup)
            logger.info(f"Start command response sent successfully to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error in start command for user {user_id}: {e}")
            import traceback
            traceback.print_exc()
            try:
                await update.message.reply_text("Sorry, something went wrong. Please try again.")
            except Exception as reply_error:
                logger.error(f"Failed to send error message: {reply_error}")
    
    async def league_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle league selection"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = update.effective_user.id
            league_key = query.data.replace("league_", "")
            
            if league_key not in LEAGUES:
                await query.edit_message_text("Invalid league selection. Please try again.")
                return
            
            league_info = LEAGUES[league_key]
            
            league_db = self.db.get_league_by_transfermarkt_id(league_info['transfermarkt_id'])
            if not league_db:
                league_id = self.db.insert_league(
                    name=league_info['name'],
                    transfermarkt_id=league_info['transfermarkt_id'],
                    season=league_info['season']
                )
            else:
                league_id = league_db['id']
            
            self.db.update_user_session(
                telegram_user_id=user_id,
                current_league_id=league_id
            )
            
            matches = self.db.get_next_matchday_matches(league_id)
            
            if not matches:
                await query.edit_message_text(
                    f"📅 No upcoming matches found for {league_info['name']}.\n"
                    "Match data might still be loading. Please try again in a few minutes."
                )
                return
            
            matchday_num = matches[0]['matchday'] if matches else 1
            
            keyboard = []
            for match in matches[:10]:  # Limit to 10 matches
                home_logo = self.logo_scraper.get_fallback_emoji(match['home_team_name'])
                away_logo = self.logo_scraper.get_fallback_emoji(match['away_team_name'])
                match_text = f"{home_logo} {match['home_team_name']} vs {match['away_team_name']} {away_logo}"
                keyboard.append([InlineKeyboardButton(
                    match_text,
                    callback_data=f"match_{match['id']}"
                )])
            
            keyboard.append([InlineKeyboardButton("🔙 Back to Leagues", callback_data="back_to_leagues")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message_text = f"🏆 {league_info['name']} - Matchday {matchday_num}\n\n📅 Matchday {matchday_num} Fixtures:\n\nSelect a match to view team lineups:"
            
            await query.edit_message_text(message_text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error in league selection: {e}")
            await query.edit_message_text("Sorry, something went wrong. Please try again.")
    
    async def match_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle match selection"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = update.effective_user.id
            match_id = int(query.data.replace("match_", ""))
            
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT m.*, 
                               ht.name as home_team_name, ht.id as home_team_id,
                               at.name as away_team_name, at.id as away_team_id,
                               l.name as league_name
                        FROM matches m
                        JOIN teams ht ON m.home_team_id = ht.id
                        JOIN teams at ON m.away_team_id = at.id
                        JOIN leagues l ON m.league_id = l.id
                        WHERE m.id = %s
                    """, (match_id,))
                    match = cursor.fetchone()
            
            if not match:
                await query.edit_message_text("Match not found. Please try again.")
                return
            
            self.db.update_user_session(
                telegram_user_id=user_id,
                current_match_id=match_id
            )
            
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT logo_url FROM teams WHERE id = %s", (match['home_team_id'],))
                    home_team_logo = cursor.fetchone()
                    cursor.execute("SELECT logo_url FROM teams WHERE id = %s", (match['away_team_id'],))
                    away_team_logo = cursor.fetchone()
            
            home_logo = self.logo_scraper.get_fallback_emoji(match['home_team_name'])
            away_logo = self.logo_scraper.get_fallback_emoji(match['away_team_name'])
            
            keyboard = [
                [InlineKeyboardButton(
                    f"{home_logo} {match['home_team_name']}", 
                    callback_data=f"team_{match['home_team_id']}"
                )],
                [InlineKeyboardButton(
                    f"{away_logo} {match['away_team_name']}", 
                    callback_data=f"team_{match['away_team_id']}"
                )],
                [InlineKeyboardButton("🔙 Back to Matches", callback_data=f"league_{match['league_name']}")],
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            match_date = match['match_date'].strftime("%B %d, %Y at %H:%M")
            message_text = (
                f"⚽ {match['home_team_name']} vs {match['away_team_name']}\n"
                f"📅 {match_date}\n"
                f"🏆 {match['league_name']}\n\n"
                "Select a team to view predicted lineup:"
            )
            
            await query.edit_message_text(message_text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error in match selection: {e}")
            await query.edit_message_text("Sorry, something went wrong. Please try again.")
    
    async def team_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle team selection and show lineup prediction"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = update.effective_user.id
            team_id = int(query.data.replace("team_", ""))
            
            session = self.db.get_user_session(user_id)
            if not session or not session['current_match_id']:
                await query.edit_message_text("Session expired. Please start over with /start")
                return
            
            match_id = session['current_match_id']
            
            self.db.update_user_session(
                telegram_user_id=user_id,
                current_team_id=team_id
            )
            
            await query.edit_message_text("🔄 Generating lineup prediction...")
            
            prediction = self.db.get_lineup_prediction(match_id, team_id)
            
            if not prediction:
                prediction = self.predictor.predict_lineup(match_id, team_id)
            
            if not prediction or prediction.get('error'):
                error_msg = prediction.get('reasoning', 'Team data might still be loading.') if prediction else 'Team data might still be loading.'
                await query.edit_message_text(
                    f"❌ Unable to generate lineup prediction.\n\n{error_msg}\n\nPlease try again later or select a different team."
                )
                return
            
            if not prediction.get('starting_xi'):
                await query.edit_message_text(
                    f"❌ Squad data incomplete.\n\n{prediction.get('reasoning', 'Team squad is still being populated.')}\n\nPlease try again later."
                )
                return
            
            message_text = await self._format_lineup_prediction(prediction, team_id, match_id)
            
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh Prediction", callback_data=f"refresh_{team_id}")],
                [InlineKeyboardButton("🔙 Back to Match", callback_data=f"match_{match_id}")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_leagues")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"Error in team selection: {e}")
            await query.edit_message_text("Sorry, something went wrong. Please try again.")
    
    async def refresh_prediction(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Refresh lineup prediction"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = update.effective_user.id
            team_id = int(query.data.replace("refresh_", ""))
            
            session = self.db.get_user_session(user_id)
            if not session or not session['current_match_id']:
                await query.edit_message_text("Session expired. Please start over with /start")
                return
            
            match_id = session['current_match_id']
            
            await query.edit_message_text("🔄 Refreshing lineup prediction...")
            
            prediction = self.predictor.predict_lineup(match_id, team_id)
            
            if not prediction:
                await query.edit_message_text(
                    "❌ Unable to refresh lineup prediction. Please try again later."
                )
                return
            
            message_text = await self._format_lineup_prediction(prediction, team_id, match_id)
            
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh Again", callback_data=f"refresh_{team_id}")],
                [InlineKeyboardButton("🔙 Back to Match", callback_data=f"match_{match_id}")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_leagues")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"Error refreshing prediction: {e}")
            await query.edit_message_text("Sorry, something went wrong. Please try again.")
    
    async def back_to_leagues(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Go back to league selection"""
        try:
            query = update.callback_query
            await query.answer()
            
            keyboard = []
            for league_key, league_info in LEAGUES.items():
                keyboard.append([InlineKeyboardButton(
                    f"{league_info['emoji']} {league_info['name']}", 
                    callback_data=f"league_{league_key}"
                )])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            welcome_message = (
                "⚽ Fantasy Football Lineup Predictor\n\n"
                "Please select a league:"
            )
            
            await query.edit_message_text(welcome_message, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error going back to leagues: {e}")
            await query.edit_message_text("Sorry, something went wrong. Please try again.")
    
    async def _format_lineup_prediction(self, prediction, team_id, match_id):
        """Format lineup prediction for display"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT name FROM teams WHERE id = %s", (team_id,))
                    team = cursor.fetchone()
                    team_name = team['name'] if team else "Unknown Team"
            
            message_parts = []
            
            message_parts.append(f"⚽ <b>{team_name} - Predicted Lineup</b>\n")
            
            formation = prediction.get('formation', 'Unknown')
            confidence = prediction.get('confidence_score', 0)
            message_parts.append(f"📋 <b>Formation:</b> {formation}")
            message_parts.append(f"🎯 <b>Confidence:</b> {confidence*100:.0f}%\n")
            
            message_parts.append("<b>🟢 Starting XI:</b>")
            starting_xi = prediction.get('starting_xi', [])
            
            if starting_xi:
                for i, player in enumerate(starting_xi, 1):
                    jersey = f"#{player.get('jersey_number', '?')}" if player.get('jersey_number') else ""
                    message_parts.append(f"{i}. {player['name']} {jersey} ({player['position']})")
            else:
                message_parts.append("No starting XI available")
            
            unavailable = prediction.get('unavailable_players', [])
            if unavailable:
                message_parts.append("\n<b>❌ Unavailable Players:</b>")
                for player in unavailable[:5]:  # Limit to 5
                    reason = player['reason'].title()
                    message_parts.append(f"• {player['name']} ({reason})")
            
            alternatives = prediction.get('alternatives', [])
            if alternatives:
                message_parts.append("\n<b>🔄 Possible Alternatives:</b>")
                for alt in alternatives[:3]:  # Limit to top 3
                    prob = alt.get('probability', 0) * 100
                    message_parts.append(f"• {alt['name']} ({prob:.0f}% chance)")
            
            reasoning = prediction.get('reasoning', '')
            if reasoning:
                message_parts.append(f"\n<b>💭 Analysis:</b>\n{reasoning}")
            
            sources = prediction.get('sources', [])
            if sources:
                message_parts.append("\n<b>📚 Sources:</b>")
                for source in sources[:2]:  # Limit to 2 sources
                    if source.get('url'):
                        message_parts.append(f"• {source.get('type', 'Source').title()}")
            
            message_parts.append(f"\n<i>Last updated: {datetime.now().strftime('%H:%M')}</i>")
            
            return "\n".join(message_parts)
            
        except Exception as e:
            logger.error(f"Error formatting lineup prediction: {e}")
            return "Error formatting prediction. Please try again."
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = (
            "⚽ <b>Fantasy Football Lineup Predictor Help</b>\n\n"
            "<b>Commands:</b>\n"
            "/start - Start the bot and select a league\n"
            "/help - Show this help message\n\n"
            "<b>How to use:</b>\n"
            "1. Select a league (EPL, La Liga, etc.)\n"
            "2. Choose an upcoming match\n"
            "3. Pick a team to see predicted lineup\n"
            "4. View starting XI, injuries, and alternatives\n\n"
            "<b>Features:</b>\n"
            "• Predicted starting lineups\n"
            "• Injury and suspension tracking\n"
            "• Alternative player suggestions\n"
            "• Formation analysis\n"
            "• Confidence scoring\n\n"
            "Data is updated every 10 hours from Transfermarkt and trusted sources."
        )
        
        await update.message.reply_text(help_text, parse_mode='HTML')
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "Sorry, an error occurred. Please try again or use /start to restart."
            )
