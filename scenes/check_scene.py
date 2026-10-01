"""Checks EO scene and story files against scene.schema.json and
story.schema.json, and the rules in README.md that a schema can't express.

    pip install jsonschema
    python check_scene.py examples/*.eoscene.json examples/*.eostory.json
"""

import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator

SCHEMA = json.loads((Path(__file__).parent / "scene.schema.json").read_text(encoding="utf-8"))
STORY_SCHEMA = json.loads((Path(__file__).parent / "story.schema.json").read_text(encoding="utf-8"))

# Cues only a personal scene may use: they act on the one player watching.
PERSONAL_ONLY = {"lock", "unlock", "camera", "screen", "choice", "map"}


def adjacent(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1


def check_compiled(scene, errors):
    cues = scene["compiled"]["cues"]
    cast = scene["cast"]
    personal = scene["kind"] == "personal"

    for index, cue in enumerate(cues):
        where = f"cue {index} ({cue['do']})"
        if cue["id"] != index:
            errors.append(f"{where}: id is {cue['id']}, but cues are numbered by position")

        branch = tuple(cue.get("branch", ()))
        if branch:
            choice, option = branch
            if choice >= index:
                errors.append(f"{where}: its branch names cue {choice}, which isn't before it")
            elif cues[choice]["do"] != "choice":
                errors.append(f"{where}: its branch names cue {choice}, which isn't a choice")
            elif option >= len(cues[choice]["options"]):
                errors.append(f"{where}: choice {choice} has no option {option}")

        for dep in cue.get("after", []):
            if dep >= index:
                errors.append(f"{where}: waits for cue {dep}, which isn't before it")
            elif tuple(cues[dep].get("branch", ())) != branch:
                errors.append(f"{where}: waits for cue {dep}, which is in a different branch")

        for field in ("actor", "follow"):
            if field in cue and cue[field] not in cast:
                errors.append(f"{where}: {field} '{cue[field]}' isn't in the cast")

        if not personal:
            if cue["do"] in PERSONAL_ONLY:
                errors.append(f"{where}: only personal scenes can {cue['do']}")
            if cue["do"] == "say" and (cue["show"] == "box" or cue["wait"] == "click"):
                errors.append(f"{where}: a world scene speaks in balloons, timed")

        if cue["do"] == "walk":
            steps = [cue["from"], *cue["path"]]
            for a, b in zip(steps, steps[1:]):
                if not adjacent(a, b):
                    errors.append(f"{where}: {a} to {b} isn't one step")
                    break

    # Each actor's walks start where it last stood. Walks inside a branch start
    # where the actor stood when the choice was made.
    where_now = {name: actor.get("at") for name, actor in cast.items()}
    for index, cue in enumerate(cues):
        if cue["do"] == "appear" and "branch" not in cue:
            where_now[cue["actor"]] = cue["at"]
        if cue["do"] == "map" and "branch" not in cue:
            # The player arrives at the map cue's tile.
            for name, actor in cast.items():
                if actor["role"] == "player":
                    where_now[name] = cue["at"]
        if cue["do"] != "walk":
            continue
        expected = where_now.get(cue["actor"])
        if expected is not None and cue["from"] != expected:
            errors.append(f"cue {index} (walk): {cue['actor']} walks from {cue['from']}, "
                          f"but stands at {expected}")
        if "branch" not in cue:
            where_now[cue["actor"]] = cue["path"][-1]

    used = {cue["do"] for cue in cues}
    listed = set(scene["compiled"].get("uses", used))
    if listed != used:
        errors.append(f"compiled.uses lists {sorted(listed)}, but the cues use {sorted(used)}")

    players = [name for name, actor in cast.items() if actor["role"] == "player"]
    if len(players) > 1 or (players and not personal):
        errors.append("only a personal scene has a player, and only one")


def check_source(scene, errors):
    source = scene.get("source")
    if not source:
        return
    clips = source.get("clips", [])
    ids = [clip["id"] for clip in clips]
    for clip_id in {i for i in ids if ids.count(i) > 1}:
        errors.append(f"source: clip id '{clip_id}' is used twice")

    known = set(ids)
    markers = source.get("markers", {})
    branches = {option["branch"] for clip in clips if clip["type"] == "choice"
                for option in clip.get("options", [])}
    for clip in clips:
        where = f"source clip '{clip['id']}'"
        for anchor in ("after", "with"):
            ref = clip["start"].get(anchor)
            if ref is not None and ref not in known:
                errors.append(f"{where}: starts {anchor} '{ref}', which isn't a clip")
        marker = clip.get("to", {}).get("marker")
        if marker is not None and marker not in markers:
            errors.append(f"{where}: walks to marker '{marker}', which isn't defined")
        for name in (clip.get("to", {}).get("near"), clip.get("toward")):
            if name is not None and name not in scene["cast"]:
                errors.append(f"{where}: '{name}' isn't in the cast")
        if "branch" in clip and clip["branch"] not in branches:
            errors.append(f"{where}: branch '{clip['branch']}' isn't an option of any choice")


def needed_scene(need):
    return need if isinstance(need, str) else need["scene"]


def check_story(path, story):
    errors = []
    if Path(path).name != f"{story['id']}.eostory.json":
        errors.append(f"the file should be named {story['id']}.eostory.json")
    beats = story["beats"]
    scenes = [beat["scene"] for beat in beats]
    for scene in {s for s in scenes if scenes.count(s) > 1}:
        errors.append(f"'{scene}' is in the story twice")
    waits = {}
    for beat in beats:
        where = f"beat '{beat['scene']}'"
        before = [needed_scene(need) for need in beat.get("after", [])]
        after_scene = beat["when"].get("afterScene")
        if after_scene:
            before.append(after_scene["scene"])
        for scene in before:
            if scene not in scenes:
                errors.append(f"{where}: waits for '{scene}', which isn't in the story")
        waits[beat["scene"]] = before
        if not (Path(path).parent / f"{beat['scene']}.eoscene.json").exists():
            print(f"     note: {beat['scene']}.eoscene.json isn't written yet")
    # Beats that wait on each other never play.
    state = {}

    def loops(scene):
        if state.get(scene) == 1:
            return True
        if state.get(scene) == 2:
            return False
        state[scene] = 1
        if any(loops(before) for before in waits.get(scene, [])):
            return True
        state[scene] = 2
        return False

    for scene in scenes:
        if loops(scene):
            errors.append(f"'{scene}' waits on itself, through the beats before it")
            break
    return errors


def check_audio(path, scene, errors):
    """Named songs, sounds and footsteps are files in the audio folder beside the scene."""
    audio = Path(path).parent / "audio"

    def found(folder, name):
        return any((audio / folder / f"{name}{ext}").exists() for ext in (".ogg", ".wav"))

    def found_sound(name):  # A file, or a set: name-1, name-2...
        return found("sounds", name) or found("sounds", f"{name}-1")

    for index, cue in enumerate(scene["compiled"]["cues"]):
        where = f"cue {index} ({cue['do']})"
        if cue["do"] == "music" and isinstance(cue.get("song"), str) and not found("music", cue["song"]):
            errors.append(f"{where}: no song '{cue['song']}' in {audio / 'music'}")
        if cue["do"] == "sound" and isinstance(cue.get("sfx"), str) and not found_sound(cue["sfx"]):
            errors.append(f"{where}: no sound '{cue['sfx']}' in {audio / 'sounds'}")
        if cue["do"] == "walk" and "steps" in cue and not found_sound(f"{cue['steps']}-step"):
            errors.append(f"{where}: no footsteps '{cue['steps']}-step' in {audio / 'sounds'}")


def check(path):
    try:
        scene = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"can't read: {error}"]

    if str(path).endswith(".eostory.json"):
        errors = [f"{'/'.join(map(str, e.absolute_path)) or '(top)'}: {e.message}"
                  for e in sorted(Draft7Validator(STORY_SCHEMA).iter_errors(scene), key=lambda e: list(e.absolute_path))]
        return errors or check_story(path, scene)

    errors = [f"{'/'.join(map(str, e.absolute_path)) or '(top)'}: {e.message}"
              for e in sorted(Draft7Validator(SCHEMA).iter_errors(scene), key=lambda e: list(e.absolute_path))]
    if errors:
        return errors  # The rules below assume the shape the schema checks.

    if Path(path).name != f"{scene['id']}.eoscene.json":
        errors.append(f"the file should be named {scene['id']}.eoscene.json")
    check_compiled(scene, errors)
    check_source(scene, errors)
    check_audio(path, scene, errors)
    return errors


def main(paths):
    failed = False
    for path in paths:
        errors = check(path)
        failed |= bool(errors)
        print(f"{'FAIL' if errors else 'ok  '} {path}")
        for error in errors:
            print(f"     {error}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
