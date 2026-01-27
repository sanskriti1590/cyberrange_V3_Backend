import logging
from datetime import datetime

from bson import ObjectId
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from database_management.pymongo_client import web_based_game_started_collection

# Set up logging
logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, default_retry_delay=60)  # Bind the task to access self.retry()
def check_and_complete_webbased_game(self, game_instance_id):
    """
    Task to check if a game has exceeded the end time, and if so, mark it as completed.
    This method updates the game instance in the database to indicate it's finished.
    Includes retry functionality in case of errors (e.g., database issues).
    """
    object_id = ObjectId(game_instance_id)
    current_time = datetime.now()

    try:
        # Fetch the game instance with minimal fields to optimize performance
        played_game = web_based_game_started_collection.find_one(
            {'_id': object_id},
            {'_id': 1, 'game_id': 1, 'player_id': 1, 'is_complete': 1, 'end_time': 1}
        )

        # Handle if the game is not found
        if not played_game:
            logger.error(f"Game instance with ID {game_instance_id} not found.")
            raise ValueError(f"Game instance with ID {game_instance_id} not found.")

        end_time = played_game.get('end_time')

        # Check if the game exists and if it hasn't already been completed
        if played_game and not played_game.get('is_complete') and end_time >= current_time:
            # Prepare the update fields for completing the game
            updated_instance = {
                "is_complete": True,
                "is_timeout_completed": True,
                "completed_at": current_time,
                "updated_at": current_time,
            }

            # Update the game instance to mark it as complete
            result = web_based_game_started_collection.update_one(
                {"_id": object_id, "is_complete": False},  # Ensures no one else completes it concurrently
                {"$set": updated_instance}
            )

            # Check if the update was successful
            if result.modified_count == 1:
                logger.info(f"Game {played_game.get('game_id')} for player {played_game.get('player_id')} is now marked as completed.")
                # Here you can also perform additional actions like updating player points, sending notifications, etc.
            else:
                logger.warning(f"Failed to mark game {played_game.get('game_id')} as completed. It might have already been completed.")
        else:
            logger.info(f"Game {played_game.get('game_id')} for player {played_game.get('player_id')} is already completed or hasn't ended yet.")

    except Exception as e:
        # Retry the task if there's an error
        logger.error(f"Error while checking and completing game {game_instance_id}: {str(e)}", exc_info=True)

        # Retry up to the defined max retries if there is an exception
        try:
            self.retry(exc=e)  # Retry the task
        except MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for game {game_instance_id}. Task will not retry further.")
