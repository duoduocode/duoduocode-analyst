from src.collector.api_client import RawMatchData
from src.composer.prompt_loader import PromptLoader
from src.engine.metrics import ComputedData, _stat


class DataBuilder:
    def __init__(self, prompt_loader: PromptLoader):
        self.pl = prompt_loader

    def build_cover(self, raw: RawMatchData, computed: ComputedData) -> tuple:
        hs = raw.home_stats
        aws = raw.away_stats
        return self.pl.render(
            "cover",
            home_team=raw.home_team.name,
            away_team=raw.away_team.name,
            home_goals=raw.score.home,
            away_goals=raw.score.away,
            halftime_home=raw.score.halftime_home,
            halftime_away=raw.score.halftime_away,
            home_possession=int(float(hs.get("Ball Possession", 50))),
            away_possession=int(float(aws.get("Ball Possession", 50))),
            home_shots=int(float(hs.get("Total Shots", 0))),
            away_shots=int(float(aws.get("Total Shots", 0))),
            home_shots_on=int(float(hs.get("Shots on Goal", 0))),
            away_shots_on=int(float(aws.get("Shots on Goal", 0))),
            home_xg=float(_stat(hs, "Expected Goals", "expected_goals", default=0)),
            away_xg=float(_stat(aws, "Expected Goals", "expected_goals", default=0)),
            home_big_chances=int(float(_stat(hs, "Big Chances Created", "Big Chances Created", default=0))),
            away_big_chances=int(float(_stat(aws, "Big Chances Created", "Big Chances Created", default=0))),
            tags="、".join(computed.tags),
        )

    def build_contrast(self, raw: RawMatchData, computed: ComputedData) -> tuple:
        hs = raw.home_stats
        aws = raw.away_stats
        return self.pl.render(
            "contrast",
            home_team=raw.home_team.name,
            away_team=raw.away_team.name,
            home_possession=int(float(hs.get("Ball Possession", 50))),
            away_possession=int(float(aws.get("Ball Possession", 50))),
            home_xg=float(_stat(hs, "Expected Goals", "expected_goals", default=0)),
            away_xg=float(_stat(aws, "Expected Goals", "expected_goals", default=0)),
            home_shots=int(float(hs.get("Total Shots", 0))),
            away_shots=int(float(aws.get("Total Shots", 0))),
            home_shots_on=int(float(hs.get("Shots on Goal", 0))),
            away_shots_on=int(float(aws.get("Shots on Goal", 0))),
            home_big_chances=int(float(hs.get("Big Chances Created", 0))),
            away_big_chances=int(float(aws.get("Big Chances Created", 0))),
            home_pass_acc=int(float(hs.get("Passes %", 75))),
            away_pass_acc=int(float(aws.get("Passes %", 75))),
            home_tackles=int(float(hs.get("Tackles", 0))),
            away_tackles=int(float(aws.get("Tackles", 0))),
        )

    def build_momentum(self, raw: RawMatchData, computed: ComputedData) -> tuple:
        segs = computed.momentum.get("segments", [])
        events = computed.momentum.get("key_events", [])
        args = {
            "home_team": raw.home_team.name,
            "away_team": raw.away_team.name,
            "events": events,
        }
        for i, seg in enumerate(segs):
            args[f"s{i}"] = seg["home"]
            args[f"r{i}"] = seg["away"]
        for i in range(6):
            args.setdefault(f"s{i}", 0)
            args.setdefault(f"r{i}", 0)
        return self.pl.render("momentum", **args)

    def build_tactics(self, raw: RawMatchData, computed: ComputedData) -> tuple:
        hs = raw.home_stats
        aws = raw.away_stats
        home_form = raw.home_lineup.formation if raw.home_lineup else "未知"
        away_form = raw.away_lineup.formation if raw.away_lineup else "未知"
        return self.pl.render(
            "tactics",
            home_team=raw.home_team.name,
            away_team=raw.away_team.name,
            home_formation=home_form,
            away_formation=away_form,
            home_attack_left=computed.home_attack_distribution.get("left", 0),
            home_attack_center=computed.home_attack_distribution.get("center", 0),
            home_attack_right=computed.home_attack_distribution.get("right", 0),
            away_attack_left=computed.away_attack_distribution.get("left", 0),
            away_attack_center=computed.away_attack_distribution.get("center", 0),
            away_attack_right=computed.away_attack_distribution.get("right", 0),
            home_long_ratio=int(computed.home_long_ball_ratio * 100),
            away_long_ratio=int(computed.away_long_ball_ratio * 100),
            home_crosses=int(float(_stat(hs, "Crosses", "Crosses", default=0))),
            away_crosses=int(float(_stat(aws, "Crosses", "Crosses", default=0))),
            home_offsides=int(float(_stat(hs, "Offsides", "Offsides", default=0))),
            away_offsides=int(float(_stat(aws, "Offsides", "Offsides", default=0))),
            home_pass_acc=int(float(_stat(hs, "Passes %", "Passes %", default=75))),
            away_pass_acc=int(float(_stat(aws, "Passes %", "Passes %", default=75))),
            home_tackles=int(float(_stat(hs, "Tackles", "Tackles", default=0))),
            away_tackles=int(float(_stat(aws, "Tackles", "Tackles", default=0))),
            home_ci=computed.home_ci,
            away_ci=computed.away_ci,
            home_pe=computed.home_pe,
            away_pe=computed.away_pe,
        )

    def build_mvp(self, player, team_name: str) -> tuple:
        if player is None:
            return ("", "该场比赛无数据")
        return self.pl.render(
            "mvp",
            player_name=player.name,
            team=team_name,
            minutes=player.minutes_played,
            rating=player.rating or 0,
            goals=player.goals,
            assists=player.assists,
            shots=player.shots_total,
            shots_on=player.shots_on,
            key_passes=player.passes_key,
            dribbles_success=player.dribbles_success,
            pass_accuracy=player.passes_accuracy,
        )

    def build_hidden_mvp(self, player, team_name: str, rating_rank: int,
                          contribution: float, contribution_rank: int) -> tuple:
        if player is None:
            return ("", "该场比赛无数据")
        duel_win_pct = (
            round(player.duels_won / max(player.duels_total, 1) * 100, 1)
            if player.duels_total > 0
            else 0
        )
        return self.pl.render(
            "hidden_mvp",
            player_name=player.name,
            team=team_name,
            minutes=player.minutes_played,
            rating=player.rating or 0,
            rating_rank=rating_rank,
            tackles=player.tackles_total,
            interceptions=player.tackles_interceptions,
            duel_win_pct=duel_win_pct,
            key_passes=player.passes_key,
            pass_accuracy=player.passes_accuracy,
            distance_covered=0,
            hidden_contribution=round(contribution, 1),
            contribution_rank=contribution_rank,
        )

    def build_black_hole(self, player, team_name: str, contribution: float) -> tuple:
        if player is None:
            return ("", "该场比赛无明显低分球员")
        duel_win_pct = (
            round(player.duels_won / max(player.duels_total, 1) * 100, 1)
            if player.duels_total > 0
            else 0
        )
        return self.pl.render(
            "black_hole",
            player_name=player.name,
            team=team_name,
            minutes=player.minutes_played,
            rating=player.rating or 0,
            shots=player.shots_total,
            shots_on=player.shots_on,
            duel_win_pct=duel_win_pct,
            duel_won=player.duels_won,
            duel_total=player.duels_total,
            fouls=player.fouls_committed,
            possession_lost=0,
            pass_accuracy=player.passes_accuracy,
            contribution=round(contribution, 1),
        )

    def build_subs(self, raw: RawMatchData, computed: ComputedData) -> tuple:
        return self.pl.render(
            "subs",
            home_team=raw.home_team.name,
            away_team=raw.away_team.name,
            home_subs=computed.home_subs_effect,
            away_subs=computed.away_subs_effect,
        )

    def build_replay(self, raw: RawMatchData, computed: ComputedData) -> tuple:
        ldi = computed.ldi_result
        top3_str = " / ".join(
            [f"{s['score']}({s['pct']}%)" for s in ldi.get("top3_scores", [])]
        )
        return self.pl.render(
            "replay",
            home_team=raw.home_team.name,
            away_team=raw.away_team.name,
            home_goals=raw.score.home,
            away_goals=raw.score.away,
            home_xg=float(_stat(raw.home_stats, "Expected Goals", "expected_goals", default=0)),
            away_xg=float(_stat(raw.away_stats, "Expected Goals", "expected_goals", default=0)),
            home_win_pct=ldi.get("home_win_pct", 0),
            draw_pct=ldi.get("draw_pct", 0),
            away_win_pct=ldi.get("away_win_pct", 0),
            top3=top3_str,
            ldi=ldi.get("ldi", 0),
            ldi_interpretation=ldi.get("interpretation", ""),
        )
