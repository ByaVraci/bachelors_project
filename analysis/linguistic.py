import sqlite3
import pandas as pd
import spacy
import nltk
from nltk.tokenize import word_tokenize
from lexicalrichness import LexicalRichness

nltk.download("punkt_tab", quiet=True)
nltk.download("stopwords", quiet=True)

nlp = spacy.load("en_core_web_sm")

# Words that indicate collaborative, uncertain,
# or negotiating tone
HEDGING_WORDS = {
    "maybe", "perhaps", "possibly", "probably",
    "might", "could", "would", "should", "seems",
    "appears", "consider", "suggest", "wonder",
    "think", "believe", "feel", "guess", "suppose"
}


def compute_lexical_diversity(text: str) -> float:
    words = str(text).split()
    if len(words) < 10:          # MTLD is unstable on very short texts
        return float("nan")      # exclude
    try:
        return LexicalRichness(str(text)).mtld()
    except Exception:
        return float("nan")

WH_WORDS = {"why", "how", "what", "where", "who", "which", "when", "whose", "whom"}

def is_question(sentence: str) -> bool:
    s = sentence.strip()
    if not s:
        return False
    if s.endswith("?"):
        return True
    first = s.lower().split()[0].strip(",.:;")
    return first in WH_WORDS      # wh-words only

def compute_question_ratio(text, mode="strict"):
    sents = list(nlp(str(text)).sents)
    if not sents:
        return 0.0
    if mode == "strict":
        q = sum(1 for s in sents if s.text.strip().endswith("?"))
    else:  # heuristic: ? OR wh-word start
        q = sum(1 for s in sents if is_question(s.text))
    return q / len(sents)

def compute_hedging_ratio(text: str) -> float:
    """
    Proportion of words that are hedging words.
    Higher ratio = more tentative, collaborative tone.
    """
    tokens = [t.lower() for t in word_tokenize(str(text))
              if t.isalpha()]
    if not tokens:
        return 0.0
    hedges = sum(1 for t in tokens if t in HEDGING_WORDS)
    return hedges / len(tokens)

def run_linguistic_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes all linguistic metrics for every comment.
    Adds columns to the DataFrame in place.
    """
    print("Computing lexical diversity...")
    df["lexical_diversity"] = df["body_clean"].apply(
        compute_lexical_diversity
    )

    print("Computing question ratio...")
    df["question_ratio"] = df["body_clean"].apply(lambda t: compute_question_ratio(t, "strict"))
    df["question_ratio_heur"] = df["body_clean"].apply(lambda t: compute_question_ratio(t, "heuristic"))

    print("Computing hedging ratio...")
    df["hedging_ratio"] = df["body_clean"].apply(
        compute_hedging_ratio
    )

    return df

def summarise_by_type(df: pd.DataFrame,
                      db_path="data/thesis.db") -> pd.DataFrame:
    """
    Adds repo type (corporate/community) to the DataFrame
    then aggregates by type and period instead of by repo.
    """
    df = df[df["word_count"] > 0]
    conn  = sqlite3.connect(db_path)
    types = pd.read_sql(
        "SELECT id AS repo_id, type FROM repositories", conn
    )
    conn.close()

    df = df.merge(types, on="repo_id", how="left")
    return df.groupby(["type", "period"]).agg(
        avg_word_count     =("word_count",        "mean"),
        avg_lex_diversity  =("lexical_diversity",  "mean"),
        avg_question_ratio =("question_ratio",     "mean"),
        avg_hedging_ratio  =("hedging_ratio",      "mean"),
        total_comments     =("id",                 "count"),
    ).round(4).reset_index()


def summarise_by_period(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates linguistic metrics by repo and period.
    = the primary comparison table.
    """
    prose = df[df["word_count"] > 0]  # linguistic metrics on prose only
    return prose.groupby(["repo_id", "period"]).agg(
        avg_word_count     =("word_count",        "mean"),
        avg_lex_diversity  =("lexical_diversity",  "mean"),
        avg_question_ratio =("question_ratio",     "mean"),
        avg_hedging_ratio  =("hedging_ratio",      "mean"),
        total_comments     =("id",                 "count"),
    ).round(4).reset_index()