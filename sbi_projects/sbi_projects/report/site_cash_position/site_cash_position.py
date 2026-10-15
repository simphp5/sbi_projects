# Copyright (c) 2026, Velmaska and contributors
from sbi_projects.cashflow import reports


def execute(filters=None):
	return reports.site_cash_position(filters)
