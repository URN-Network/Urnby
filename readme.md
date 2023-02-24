Transparency
	Due to the nature of this group, newly formed with limited to no affiliation to other members, my aim is to be fully transparent on records and data to empower users to be able to question this system to form a bond of trust.
	
	My method for doing this is implementing permissions to allow anyone to read any and all data created by the bot in various forms and views.
	
	These permissions will provide a framework for normal functionality, BUT IT IS UP TO USERS TO CROSS CHECK INFORMATION AND SPEAK UP IF THERE ARE CONCERNS OF ABUSE BY MEMBERS OR ADMINS.
	
Technical Info
	This bot application was made in python3 using the pycord library and (currently) json files (transitioning to sqlite3) as the database system.
	Builtin python libraries used:
	os - getting environment variables
	datetime - common datetime functionality
	pathlib - Transitioning out after data switch to sqlite
	json - Transitioning out after data switch to sqlite
	
	Python dependancies are:
	pycord - Python Discord API wrapper
	dotenv - allows us to store secrets in environment, ignoreing the .env file to share code without sharing secrets (https://12factor.net/config)
	pytz - Functionality for datetime timezones
	aiosqlite - Non blocking wrapper for sqlite-python interfacing
	
	SQLite has WAL mode enabled to allow concurrent read/writes (https://www.sqlite.org/walformat.html)
	
	Helpful links on pycord development from the following:
	https://github.com/Pycord-Development/pycord/tree/master/examples


Permissions

	There will be three tiers of Users; Guests, Members, and Administrators.
		Guests - Will only be able to read bot configuration 
		Members - Will have common use abilities of the bot to function normally, most functions outside of reading data will need to be ran in acceptable channels (hereby known as 'public channels'), which are defined in the config
		Admin - Will have ability to edit and potentially delete existing data, these commands can only be performed in chat channels with the member role able to see message history. Users will be able to read command logs in case of deleted commands/config changes.
	
	At this time all commands will be logged. All commands will be self referenced (no one can clock in for another user) except for some admin functions
	
	Permissions commonly come in the form of an acronym CRUD (Create, Read, Update, and Delete.) I'll split functionality by these components.
	
	I'll try to provide consise information on each model currently available (Config, Activity, Session, Historical):
	(All Models): 
		Read: All users (for config) and all members+ (for higher permissions functions, essentially all but config) can read all models of data and will return an ephemeral (invisible to others) message, unless provided an optional parameter to be public. 
		Create: Must be ran in public channels, non-ephemeral
		Delete: Must be ran in public channels, non-ephemeral
		Edit: Must be ran in public channels, non-ephemeral
	
	Config:
		Consists of the following values: Role required for higher permission functions, and "public channel" information.
		Read: All users. Only function allowed for all Users in all guild channels, but not DMs
		Create: Disabled - Bot managed
		Delete: Disabled - Bot manditory
		Edit: Admins 
	
	Activity:
		Read: All members 
		Create: (aka 'clockin') All members
		Delete: (aka 'clockout') All members - bot managed on session end command
		Edit - CharacterName: All members
		Edit - Starttime: Admins
		
	Session:
		Read: All members
		Create: (aka startsession) All members
		Delete: (aka endsession) All members
		Edit - Sessionname: All members
		Edit - Starttime: Admins
		
	Activity Historical:
		Read: All members
		Create: Disabled - Bot managed
		Delete: Disabled. Maybe admins in public channels?
		Edit: Admins
	
	
	Session History (In development):
		Read: All members
		Create: Disabled
		Delete: Disabled
		Edit: Disabled
		
	Clear Out History (aka you got an urn, In development, transitioning from historical info):
		Read: All members
		Create: All members
		Delete: Admins
		Edit: Admins
	
	Peeping Functions (aka other group has camp, allows communcation on who has kept track of their camp in a silent method):
		Read: (aka whopeeped) All members
		Create: (aka ipeeped) All members
		Delete: Disabled - Bot managed
		Edit: Disabled - No need recreate peep
	
	Camp Queue (In development):
		Read: All members
		Create: All members
		Delete: All members
		Edit: All members
		
	Command History (In development):
		Read: All members
		Create: Disabled - Bot managed
		Delete: Disabled
		Edit: Disabled
	
	Export Functionality (In development):
		Read: All members
		Create: Disabled
		Delete: Disabled
		Edit: Disabled
	