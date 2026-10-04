from datetime import datetime
from pathlib import Path
import math
import shutil
import sqlite3

import pandas as pd
import streamlit as st


st.set_page_config(page_title="森林調査ノート", layout="wide")

st.title("森林調査ノート")
st.write("班ごとの森林調査記録を入力し、集計するアプリです。")

folder = Path(__file__).parent
added_path = folder / "added_records.csv"
db_path = folder / "forest_records.db"
backup_dir = folder / "backups"

COLUMNS = [
    "班",
    "調査区域",
    "樹種",
    "胸高直径（cm）",
    "樹高（m）",
    "個体番号",
]
REQUIRED_COLUMNS = ["班", "調査区域", "樹種", "個体番号"]
NUMBER_COLUMNS = ["胸高直径（cm）", "樹高（m）"]
KEY_COLUMNS = ["班", "調査区域", "個体番号"]


def normalize_column_name(name):
    name = str(name).strip().replace(" ", "").replace("　", "")
    name = name.replace("ｍ", "m").replace("(", "（").replace(")", "）")
    return name


def normalize_frame(frame):
    frame = frame.copy()
    rename_map = {column: normalize_column_name(column) for column in frame.columns}
    frame = frame.rename(columns=rename_map)
    return frame.reindex(columns=COLUMNS)


def to_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def to_number(value):
    if pd.isna(value):
        return 0.0
    return float(value)


def open_database():
    connection = sqlite3.connect(db_path, timeout=30)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database():
    backup_dir.mkdir(exist_ok=True)
    with open_database() as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS forest_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team TEXT NOT NULL,
                area TEXT NOT NULL,
                species TEXT NOT NULL,
                diameter REAL NOT NULL,
                height REAL NOT NULL,
                tree_id TEXT NOT NULL,
                UNIQUE (team, area, tree_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL
            )
            """
        )
        migration_done = connection.execute(
            "SELECT setting_value FROM app_settings WHERE setting_key = 'csv_migrated'"
        ).fetchone()

        if migration_done is None:
            imported_count = 0
            if added_path.exists():
                # CSVは移行元としてそのまま残し、別にコピーも保管する
                csv_backup = backup_dir / "added_records_before_sqlite.csv"
                if not csv_backup.exists():
                    shutil.copy2(added_path, csv_backup)

                old_df = normalize_frame(
                    pd.read_csv(added_path, encoding="utf-8-sig")
                )
                for _, row in old_df.iterrows():
                    try:
                        connection.execute(
                            """
                            INSERT OR IGNORE INTO forest_records
                                (team, area, species, diameter, height, tree_id)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                to_text(row["班"]),
                                to_text(row["調査区域"]),
                                to_text(row["樹種"]),
                                to_number(row["胸高直径（cm）"]),
                                to_number(row["樹高（m）"]),
                                to_text(row["個体番号"]),
                            ),
                        )
                        imported_count += connection.execute(
                            "SELECT changes()"
                        ).fetchone()[0]
                    except (TypeError, ValueError):
                        continue

            connection.execute(
                """
                INSERT INTO app_settings (setting_key, setting_value)
                VALUES ('csv_migrated', 'yes')
                """
            )
            return imported_count

    return None


def load_added_records():
    with open_database() as connection:
        rows = connection.execute(
            """
            SELECT id, team, area, species, diameter, height, tree_id
            FROM forest_records
            ORDER BY id
            """
        ).fetchall()

    records = []
    for record_id, team, area, species, diameter, height, tree_id in rows:
        records.append(
            {
                "record_id": record_id,
                "班": team,
                "調査区域": area,
                "樹種": species,
                "胸高直径（cm）": diameter,
                "樹高（m）": height,
                "個体番号": tree_id,
            }
        )
    return pd.DataFrame(records, columns=["record_id", *COLUMNS])


def backup_database():
    backup_dir.mkdir(exist_ok=True)
    if not db_path.exists():
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = backup_dir / f"forest_records_{stamp}.db"
    with sqlite3.connect(db_path, timeout=30) as source:
        with sqlite3.connect(backup_path) as destination:
            source.backup(destination)


def insert_record(record):
    with open_database() as connection:
        connection.execute(
            """
            INSERT INTO forest_records
                (team, area, species, diameter, height, tree_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record["班"],
                record["調査区域"],
                record["樹種"],
                float(record["胸高直径（cm）"]),
                float(record["樹高（m）"]),
                record["個体番号"],
            ),
        )


def update_records(record_ids, frame):
    with open_database() as connection:
        for record_id, (_, row) in zip(record_ids, frame.iterrows()):
            connection.execute(
                """
                UPDATE forest_records
                SET team = ?, area = ?, species = ?, diameter = ?, height = ?, tree_id = ?
                WHERE id = ?
                """,
                (
                    row["班"],
                    row["調査区域"],
                    row["樹種"],
                    float(row["胸高直径（cm）"]),
                    float(row["樹高（m）"]),
                    row["個体番号"],
                    int(record_id),
                ),
            )


def duplicate_mask(frame):
    keys = frame[KEY_COLUMNS].fillna("").astype(str)
    keys = keys.apply(lambda column: column.str.strip())
    complete_key = keys.ne("").all(axis=1)
    return complete_key & keys.duplicated(keep=False)


migration_count = initialize_database()
if migration_count is not None:
    st.info(f"以前のCSVから {migration_count} 件の追加記録をSQLiteへ移しました。CSVも移行元として残しています。")

added_df = load_added_records()
all_df = added_df[COLUMNS].copy()

notice = st.session_state.pop("forest_notice", None)
if notice:
    st.success(notice)

st.caption(
    "このアプリに登録した記録だけを表示・集計します。記録は forest_records.db に保存されます。"
    "公開デモでは架空データを使ってください。Cloudでは保存が保証されないため、必要な記録はCSVで保存してください。"
)

st.subheader("新しい調査記録を入力")
with st.form("record_form"):
    team = st.selectbox("班", ["1班", "2班", "3班"])
    area = st.text_input("調査区域", placeholder="例：A")
    tree_id = st.text_input("個体番号", placeholder="例：A1")
    species = st.text_input("樹種", placeholder="例：スギ、ヒノキ")
    diameter = st.number_input(
        "胸高直径（cm）", min_value=0.0, value=20.0, step=0.1
    )
    height = st.number_input(
        "樹高（m）", min_value=0.0, value=15.0, step=0.1
    )
    submitted = st.form_submit_button("記録を追加")

if submitted:
    area = area.strip()
    tree_id = tree_id.strip()
    species = species.strip()

    if not area or not tree_id or not species:
        st.error("調査区域・個体番号・樹種を入力してください。")
    else:
        existing_keys = all_df[KEY_COLUMNS].fillna("").astype(str)
        existing_keys = existing_keys.apply(lambda column: column.str.strip())
        duplicate = (
            (existing_keys["班"] == team)
            & (existing_keys["調査区域"] == area)
            & (existing_keys["個体番号"] == tree_id)
        ).any()

        if duplicate:
            st.error("この班・調査区域・個体番号の記録は、すでにあります。")
        else:
            new_record = {
                "班": team,
                "調査区域": area,
                "樹種": species,
                "胸高直径（cm）": diameter,
                "樹高（m）": height,
                "個体番号": tree_id,
            }
            try:
                backup_database()
                insert_record(new_record)
                st.session_state["forest_notice"] = "記録を追加しました。"
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("同じ記録がほかの人から先に登録されました。入力内容を確認してください。")
            except sqlite3.Error as error:
                st.error(f"データベースへの保存に失敗しました: {error}")

st.sidebar.header("絞り込み")
team_options = ["すべて"] + sorted(
    all_df["班"].dropna().astype(str).unique().tolist()
)
selected_team = st.sidebar.selectbox("班で絞り込む", team_options)

filtered_df = all_df.copy()
if selected_team != "すべて":
    filtered_df = filtered_df[filtered_df["班"].astype(str) == selected_team]

species_filters = ["すべて"] + sorted(
    filtered_df["樹種"].dropna().astype(str).unique().tolist()
)
selected_species = st.sidebar.selectbox("樹種で絞り込む", species_filters)
if selected_species != "すべて":
    filtered_df = filtered_df[filtered_df["樹種"].astype(str) == selected_species]

st.subheader("集計")
col1, col2 = st.columns(2)
col1.metric("表示中の記録数", f"{len(filtered_df)} 本")
col2.metric("樹種の種類", f"{filtered_df['樹種'].nunique()} 種")

st.subheader("樹種ごとの本数")
species_counts = (
    filtered_df.groupby("樹種")
    .size()
    .reset_index(name="本数")
)
st.dataframe(species_counts, width="stretch", hide_index=True)

st.subheader("調査記録")
st.dataframe(filtered_df, width="stretch", hide_index=True)

csv_data = all_df.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "全調査記録をCSVでダウンロード",
    csv_data,
    file_name="森林調査記録.csv",
    mime="text/csv",
)

st.subheader("記録の修正")
st.caption("このアプリに登録した記録を修正できます。")
st.caption("記録IDは保存用の番号です。変更しないでください。")

if added_df.empty:
    st.info("修正できる記録はまだありません。")
else:
    editor_df = added_df[["record_id", *COLUMNS]]
    edited_df = st.data_editor(
        editor_df,
        width="stretch",
        hide_index=True,
        num_rows="fixed",
        disabled=["record_id"],
        column_config={
            "班": st.column_config.SelectboxColumn(
                "班", options=["1班", "2班", "3班"], required=True
            ),
            "調査区域": st.column_config.TextColumn("調査区域", required=True),
            "樹種": st.column_config.TextColumn("樹種", required=True),
            "胸高直径（cm）": st.column_config.NumberColumn(
                "胸高直径（cm）", min_value=0.0, step=0.1
            ),
            "樹高（m）": st.column_config.NumberColumn(
                "樹高（m）", min_value=0.0, step=0.1
            ),
            "個体番号": st.column_config.TextColumn("個体番号", required=True),
        },
        key="edit_added_records",
    )

    if st.button("修正内容を保存"):
        candidate_df = normalize_frame(edited_df[COLUMNS])
        record_ids = edited_df["record_id"].tolist()

        missing_mask = candidate_df[REQUIRED_COLUMNS].apply(
            lambda column: column.fillna("").astype(str).str.strip().eq("")
        ).any(axis=1)

        number_error = False
        for column in NUMBER_COLUMNS:
            values = pd.to_numeric(candidate_df[column], errors="coerce")
            if values.isna().any() or (values < 0).any():
                number_error = True
            elif not all(math.isfinite(float(value)) for value in values):
                number_error = True

        has_duplicates = duplicate_mask(candidate_df).any()

        if missing_mask.any():
            st.error("班・調査区域・樹種・個体番号は空欄にできません。")
        elif number_error:
            st.error("胸高直径と樹高には、0以上の数値を入力してください。")
        elif has_duplicates:
            st.error("班・調査区域・個体番号が重複しています。重複を直してから保存してください。")
        else:
            try:
                backup_database()
                update_records(record_ids, candidate_df)
                st.session_state["forest_notice"] = "修正した記録を保存しました。"
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("同じ個体番号の記録が重複するため保存できませんでした。")
            except sqlite3.Error as error:
                st.error(f"修正内容の保存に失敗しました: {error}")

