#!/bin/sh
set -e

# This script will
#   * create a new file `dearmep.sqlite` and initialize it
#   * download the current MEP dump from Parltrack (except when it already has
#     an up to date copy)
#   * convert the dump to DearMEP Destination JSON

ME='build-db.sh'
BASEDIR='build-db'
DB_FILE='dearmep.sqlite'
MEP_DUMP_URL='https://parltrack.org/dumps/ep_meps.json.lz'
MEP_DUMP="$BASEDIR/ep_meps.json.lz"
DESTINATION_JSON="$BASEDIR/destinations.ndjson"
PORTRAIT_DIR="$BASEDIR/portraits"
LOGO_DIR="$BASEDIR/logos"
SWAYABILITY="$BASEDIR/2023-05-04-swayability.csv"

msg() {
	printf '%s: %s\n' "$ME" "$*"
}

err() {
	msg "$*" >&2
}

die() {
	rc="$1"; shift
	err "$*"
	exit "$rc"
}

check_basedir() {
	if ! [ -d "$BASEDIR" ]; then
		die 2 "Base directory $BASEDIR does not exist, please create."
	fi
}

init_db() {
	if [ -e "$DB_FILE" ]; then
		die 3 "Database $DB_FILE already exists, refusing to overwrite."
	fi
	msg 'Initializing database.'
	dearmep db init
	msg 'Database initialized.'
}

download_mep_dump() {
	msg "Downloading MEP dump from $MEP_DUMP_URL."
	curl -o "$MEP_DUMP" --time-cond "$MEP_DUMP" "$MEP_DUMP_URL"
	msg 'Downloaded MEP dump.'
}

create_destination_json() {
	msg 'Converting MEP dump into Destination JSON.'
	dearmep convert parltrack.meps "$MEP_DUMP" > "$DESTINATION_JSON"
}

download_portraits() {
	if ! [ -d "$PORTRAIT_DIR" ]; then
		msg "Creating portrait directory $PORTRAIT_DIR."
		mkdir "$PORTRAIT_DIR"
	fi
	msg "Downloading portraits into $PORTRAIT_DIR."
	in2csv -f ndjson "$DESTINATION_JSON" \
	| csvgrep -c '_dearmep_type' -m 'destination' \
	| csvcut -c 'id' \
	| tail -n +2 \
	| xargs dearmep convert europarl.portraits \
		--filename-template "$PORTRAIT_DIR/{id}.jpg" \
		--existing skip \
		--not-found ignore
	msg 'Downloading placeholder image.'
	dearmep convert europarl.portraits \
		--filename-template "$PORTRAIT_DIR/placeholder.jpg" \
		--existing skip \
		--not-found save \
		0
	msg 'Downloaded portraits.'
}

import_destinations() {
	msg 'Importing Destinations into database.'
	dearmep import destinations \
		--portrait-template "$PORTRAIT_DIR/{filename}" \
		--fallback-portrait "$PORTRAIT_DIR/placeholder.jpg" \
		--logo-template "$LOGO_DIR/{filename}" \
		"$DESTINATION_JSON"
	msg 'Destinations imported.'
}

import_swayability() {
	msg 'Importing Base Endorsement into database.'
	dearmep import swayability \
		--ignore-unknown \
		"$SWAYABILITY"
	msg 'Imported Base Endorsement.'
}

check_basedir
init_db
download_mep_dump
create_destination_json
download_portraits
import_destinations
import_swayability
