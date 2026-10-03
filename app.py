from datetime import date

import pandas as pd
import streamlit as st

st.set_page_config(page_title="森林調査ノート | デモ", layout="wide")
st.title("森林調査ノート")
st.caption("就職活動用のデモです。表示される森林データはすべて架空です。")

if "records" not in st.session_state:
    st.session_state.records = [
        {"班": "1班", "調査区域": "A", "個体番号": "A1", "樹種": "ヒノキ", "胸高直径（cm）": 20.0, "樹高（m）": 15.0},
        {"班": "2班", "調査区域": "B", "個体番号": "B1", "樹種": "スギ", "胸高直径（cm）": 19.0, "樹高（m）": 17.0},
        {"班": "1班", "調査区域": "A", "個体番号": "A2", "樹種": "スギ", "胸高直径（cm）": 23.0, "樹高（m）": 14.0},
        {"班": "2班", "調査区域": "B", "個体番号": "B2", "樹種": "ヒノキ", "胸高直径（cm）": 26.0, "樹高（m）": 19.0},
        {"班": "3班", "調査区域": "C", "個体番号": "C1", "樹種": "ヒノキ", "胸高直径（cm）": 18.0, "樹高（m）": 20.0},
        {"班": "3班", "調査区域": "C", "個体番号": "C2", "樹種": "ヒノキ", "胸高直径（cm）": 19.0, "樹高（m）": 17.0},
    ]

with st.expander("調査記録を追加", expanded=True):
    with st.form("record_form"):
        left, right = st.columns(2)
        with left:
            team = st.selectbox("班", ["1班", "2班", "3班"])
            area = st.text_input("調査区域", placeholder="例：A")
            tree_id = st.text_input("個体番号", placeholder="例：A3")
        with right:
            species = st.selectbox("樹種", ["ヒノキ", "スギ", "カラマツ", "その他"])
            diameter = st.number_input("胸高直径（cm）", min_value=0.0, value=20.0, step=0.1)
            height = st.number_input("樹高（m）", min_value=0.0, value=15.0, step=0.1)
        submitted = st.form_submit_button("記録を追加")

if submitted:
    if not area.strip() or not tree_id.strip():
        st.error("調査区域と個体番号を入力してください。")
    else:
        st.session_state.records.append(
            {
                "班": team,
                "調査区域": area.strip(),
                "個体番号": tree_id.strip(),
                "樹種": species,
                "胸高直径（cm）": diameter,
                "樹高（m）": height,
            }
        )
        st.success("この画面のデモ記録に追加しました。")

df = pd.DataFrame(st.session_state.records)
st.sidebar.header("絞り込み")
teams = ["すべて"] + sorted(df["班"].unique().tolist())
selected_team = st.sidebar.selectbox("班", teams)
filtered_df = df if selected_team == "すべて" else df[df["班"] == selected_team]
species_options = ["すべて"] + sorted(filtered_df["樹種"].unique().tolist())
selected_species = st.sidebar.selectbox("樹種", species_options)
if selected_species != "すべて":
    filtered_df = filtered_df[filtered_df["樹種"] == selected_species]

st.subheader("集計")
first, second = st.columns(2)
first.metric("表示中の記録数", f"{len(filtered_df)} 本")
second.metric("樹種の種類", f"{filtered_df['樹種'].nunique()} 種")
st.subheader("樹種ごとの本数")
counts = filtered_df.groupby("樹種").size().reset_index(name="本数")
st.dataframe(counts, use_container_width=True, hide_index=True)
st.subheader("調査記録")
st.dataframe(filtered_df, use_container_width=True, hide_index=True)
st.download_button(
    "表示中の記録をCSVでダウンロード",
    data=filtered_df.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"forest_records_{date.today().isoformat()}.csv",
    mime="text/csv",
)
st.caption("この公開デモの入力内容はブラウザーのセッション内だけで扱います。実運用データの保存には使わないでください。")
