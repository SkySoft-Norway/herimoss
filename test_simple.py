try:
	import generate_enhanced_calendar as g
	html = g.generate_simple_listing(use_mariadb=g.HAS_MYSQL)
	print('HAS_NAV', '#oversikt' in html)
	print('HAS_TIPS', 'tipsForm' in html)
	print(html[:500])
except Exception as e:
	import traceback, sys
	print('ERROR', e)
	traceback.print_exc()