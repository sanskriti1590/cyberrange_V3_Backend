from celery import shared_task

from .serializers import CTFDeleteGameSerializer


@shared_task
def delete_ctf_game_task(ctf_game_id, user_id):
    serializer = CTFDeleteGameSerializer()
    ctf_archive_game = serializer.delete_game(ctf_game_id, user_id)
    return ctf_archive_game