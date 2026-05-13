from datetime import date, timedelta


def calculate_week_and_due_date(lmp_date: date):
    today = date.today()
    days_diff = (today - lmp_date).days
    current_week = max(1, (days_diff // 7) + 1)
    due_date = lmp_date + timedelta(days=280)
    return current_week, due_date


def calculate_trimester_dates(lmp_date: date):
    second_trimester = lmp_date + timedelta(days=91)
    third_trimester = lmp_date + timedelta(days=182)
    return second_trimester, third_trimester
