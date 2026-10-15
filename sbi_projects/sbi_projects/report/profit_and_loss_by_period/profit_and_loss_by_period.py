# Copyright (c) 2026, Velmaska and contributors
from sbi_projects.cashflow import reports


def execute(filters=None):
	return reports.profit_by_period(filters)
