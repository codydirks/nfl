import nflgame

scores = {}
printed_punts = {}


def calc_field_pos_score(play):
    yrdln = play.data['yrdln']
    yrdlnInt = int(yrdln.split(' ')[-1])

    if '50' in play.data['yrdln']:
        return (1.1) ** 10
    elif play.data['posteam'] in play.data['yrdln']:
        return max(1., (1.1) ** (yrdlnInt - 40))
    else:
        return (1.2) ** (50-yrdlnInt) * (1.1) ** 10


def calc_yds_to_go_multiplier(play):
    if play.data['ydstogo'] >= 10:
        return 0.2
    elif play.data['ydstogo'] >= 7:
        return 0.4
    elif play.data['ydstogo'] >= 4:
        return 0.6
    elif play.data['ydstogo'] >= 2:
        return 0.8
    else:
        return 1


def calc_score_multiplier(play):
    # 1x if winning
    # 2x if tied
    # 3x if down by >8pts
    # 4x if down by <=8pts
    points_diff = calc_score_diff(play)
    if points_diff > 0:
        return 1.
    elif points_diff == 0:
        return 2.
    elif points_diff >= -8:
        return 4.
    else:
        return 3.


def calc_clock_multiplier(play):
    if play.data['qtr'] > 2 and calc_score_diff(play) <= 0:
        num_seconds = calc_sec_since_half(play)
        return ((num_seconds * 0.001) ** 3) + 1
    else:
        return 1.


def process_touchdown(drive):
    total_points = 6
    pat = list(drive.plays)[-1]
    if 'extra point is GOOD' in pat.desc:
        total_points += 1
    elif 'ATTEMPT SUCCEEDS' in pat.desc:
        total_points += 2
    elif drive.result in ('Fumble', 'Interception'):
        total_points += 1
    if 'TOUCHDOWN NULLIFIED' in pat.desc:
        total_points = 0
    return total_points


def calc_score_diff(play):
    """
    Calculates the score difference at the point in the game
    when the given play occurred.

    Parameters:
    play(nflgame.game.Play): The play in question

    Returns:
    int: The score differential of the team with possession.
         Positive == winning, negative == losing
    """

    def process_touchdown(drive):
        total_points = 6
        pat = list(drive.plays)[-1]
        if 'extra point is GOOD' in pat.desc:
            total_points += 1
        elif 'ATTEMPT SUCCEEDS' in pat.desc:
            total_points += 2
        elif drive.result in ('Fumble', 'Interception'):
            total_points += 1
        if 'TOUCHDOWN NULLIFIED' in pat.desc:
            total_points = 0
        return total_points
    home_team = play.drive.game.home
    away_team = play.drive.game.away
    score = {away_team: 0, home_team: 0}

    drives = [d for d in play.drive.game.drives if d.drive_num < play.drive.drive_num]
    for drive in drives:
        if drive.result == 'Field Goal':
            score[drive.team] += 3
        elif 'Safety' in drive.result:
            if drive.team == home_team:
                score[away_team] += 2
            else:
                score[home_team] += 2
        elif drive.result == 'Touchdown':
            score[drive.team] += process_touchdown(drive)
        elif drive.result in ('Fumble', 'Interception') and any([p.touchdown for p in drive.plays]):
            if drive.team == home_team:
                score[away_team] += process_touchdown(drive)
            else:
                score[home_team] += process_touchdown(drive)

    points_diff = score[home_team] - score[away_team]
    if play.data['posteam'] == home_team:
        return int(points_diff)
    else:
        return int(-points_diff)


def calc_sec_since_half(play):
    def calc_sec_from_str(time_str: str):
        """
        Calculates the integer number of seconds from a given
        time string of the format MM:SS
        """
        mn, sc = map(int, time_str.split(':'))
        return mn * 60 + sc
    if play.data['qtr'] <= 2:
        return 0.

    if play.drive.game.schedule['year'] >= 2018:
        ot_len = 10
    else:
        ot_len = 15

    if play.drive.game.schedule['season_type'] != 'POST' and play.data['qtr'] == 5:
        sec_in_qtr = (ot_len * 60) - calc_sec_from_str(play.data['time'])
    else:
        sec_in_qtr = (15 * 60) - calc_sec_from_str(play.data['time'])
    return max(sec_in_qtr + (15 * 60) * (play.data['qtr'] - 3), 0)


def calc_yd_line_int(play):
    """
    Calculates the yard line as an integer b/w 0 - 100,
    where 0 - 50 represents the opponent's side of the field,
    and 50 - 100 represents the possessing team's side.
    """
    if play.data['yrdln'] == '':
        return None
    if play.data['yrdln'] == '50':
        return 50
    side, yrdln = play.data['yrdln'].split(' ')
    yrdln = int(yrdln)
    if play.data['posteam'] == side:
        return yrdln
    else:
        return 100 - yrdln


def calc_surrender_index(play):
    return calc_field_pos_score(play) * calc_yds_to_go_multiplier(play) *\
        calc_score_multiplier(play) * calc_clock_multiplier(play)


def update_scores(game):
    global scores
    scores[game.home] = game.score_home
    scores[game.away] = game.score_away


def is_punt(play):
    return (('punts' in play.desc.lower() or 'punt is blocked' in play.desc.lower())
            and 'no play' not in play.desc.lower())


def has_been_printed(play):
    game = scores.get(play.drive.game.gamekey, [])
    return play.playid in game


def update_printed_plays(play):
    game = scores.get(play.drive.game.gamekey, [])
    game.append(play.playid)
    scores[play.drive.game.gamekey] = game


def live_callback(active, completed, diffs):
    for game in active:
        update_scores(game)

    for diff in diffs:
        for play in diff.plays:
            away = play.drive.game.away
            home = play.drive.game.home
            if is_punt(play) and has_been_printed(play) is False:
                print(f"Q{play.data['qtr']}", play.data['time'], end='   ')
                print(f'{away} {scores[away]} - {home} {scores[home]}')
                print(play.desc)
                print('Surrender Index: {:>6.2f}'.format(calc_surrender_index(play)))
                print()
                update_printed_plays(play)


def main():
    print('Starting up live listener...')
    while True:
        try:
            nflgame.live.run(live_callback, active_interval=15,
                             inactive_interval=900, stop=None)
        except Exception as e:
            print('Error occurred:')
            print(e)
            print()


if __name__ == '__main__':
    main()
