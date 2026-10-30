"""APScheduler service — runs nightly ingest + Monday curation."""
from apscheduler.schedulers.blocking import BlockingScheduler
from app.jobs.nightly import run_nightly
from app.jobs.monday_feed import run_monday_curation


def main():
    sched = BlockingScheduler(timezone="Asia/Kolkata")
    sched.add_job(lambda: run_nightly(100), "cron", hour=3, minute=0, id="nightly")
    sched.add_job(run_monday_curation, "cron", day_of_week="mon", hour=6, minute=0, id="monday")
    print("Scheduler started. Jobs: nightly@3AM IST, monday@6AM IST")
    sched.start()


if __name__ == "__main__":
    main()
