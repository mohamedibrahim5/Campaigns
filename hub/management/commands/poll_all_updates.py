import sys
import time
import signal
import subprocess
from typing import List

from django.core.management.base import BaseCommand, CommandError
from hub.models import Bot


class Command(BaseCommand):
    help = "Run poll_updates for all active bots in parallel (one command)."

    def add_arguments(self, parser):
        parser.add_argument('--timeout', type=int, default=50, help='Long poll timeout seconds passed to poll_updates')
        parser.add_argument('--sleep', type=int, default=1, help='Sleep between polls when no updates, passed to poll_updates')

    def handle(self, *args, **options):
        timeout = int(options.get('timeout') or 50)
        sleep_sec = int(options.get('sleep') or 1)

        bots: List[Bot] = list(Bot.objects.filter(is_active=True))
        if not bots:
            raise CommandError('No active bots found.')

        self.stdout.write(self.style.SUCCESS(f"Launching pollers for {len(bots)} active bot(s)..."))

        processes: List[subprocess.Popen] = []

        try:
            for b in bots:
                cmd = [
                    sys.executable,
                    'manage.py',
                    'poll_updates',
                    '--bot-id', str(b.id),
                    '--timeout', str(timeout),
                    '--sleep', str(sleep_sec),
                ]
                proc = subprocess.Popen(cmd)
                processes.append(proc)
                self.stdout.write(self.style.SUCCESS(f" → Started poll_updates for bot '{b.name}' (id={b.id}) pid={proc.pid}"))

            # Wait indefinitely until Ctrl+C
            while True:
                time.sleep(5)

        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('Stopping all pollers (KeyboardInterrupt)...'))
        finally:
            # Terminate all subprocesses
            for p in processes:
                try:
                    p.send_signal(signal.SIGINT)
                except Exception:
                    pass
            for p in processes:
                try:
                    p.wait(timeout=5)
                except Exception:
                    try:
                        p.kill()
                    except Exception:
                        pass
            self.stdout.write(self.style.SUCCESS('All pollers stopped.'))


