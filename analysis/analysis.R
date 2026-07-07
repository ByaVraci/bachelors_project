packages <- c("tidyverse","lme4","lmerTest","rstatix","ggpubr",
              "broom.mixed","knitr","scales")
to_install <- packages[!packages %in% rownames(installed.packages())]
if (length(to_install)) install.packages(to_install)

library(tidyverse); library(lme4); library(lmerTest)
library(rstatix);   library(ggpubr); library(broom.mixed)
library(knitr);     library(scales)

RESULTS_DIR <- "results"
dir.create(file.path(RESULTS_DIR, "plots"), showWarnings = FALSE)

PALETTE <- c("pre_ai" = "#5B8DB8", "post_ai" = "#C96A50")
LABELS  <- c("pre_ai" = "Pre-AI",  "post_ai" = "Post-AI")

#1. Load data
na_strings <- c("", "NA", "NaN")

comments <- read_csv(file.path(RESULTS_DIR, "comments_for_r.csv"),
                     na = na_strings, show_col_types = FALSE) %>%
  mutate(period  = factor(period, levels = c("pre_ai","post_ai")),
         type    = factor(type,   levels = c("community","corporate")),
         repo_id = factor(repo_id))

pr_level <- read_csv(file.path(RESULTS_DIR, "pr_level_for_r.csv"),
                     na = na_strings, show_col_types = FALSE) %>%
  mutate(period  = factor(period, levels = c("pre_ai","post_ai")),
         type    = factor(type,   levels = c("community","corporate")),
         repo_id = factor(repo_id))

prs <- read_csv(file.path(RESULTS_DIR, "prs_for_r.csv"),
                na = na_strings, show_col_types = FALSE)

# Comment-level linguistic/sentiment analysis uses prose only,
# matching the Python summaries (empty/code-only rows excluded).
comments_prose <- comments %>% filter(word_count > 0)

cat(sprintf("Loaded %d comments (%d prose) across %d PRs\n",
            nrow(comments), nrow(comments_prose),
            n_distinct(comments$pr_id)))

# How many comments survive the prose filter, per period?
print(comments %>% count(period, prose = word_count > 0))

# 2. Descriptive statistics
cat("\n=== Descriptives: comment level ===\n")
desc_comments <- comments_prose %>%
  group_by(repo_id, period) %>%
  summarise(n = n(),
            avg_word_count    = mean(word_count, na.rm = TRUE),
            avg_lex_mtld      = mean(lexical_diversity, na.rm = TRUE),
            avg_question      = mean(question_ratio, na.rm = TRUE),
            avg_question_heur = mean(question_ratio_heur, na.rm = TRUE),
            avg_hedging       = mean(hedging_ratio, na.rm = TRUE),
            avg_polarity      = mean(polarity, na.rm = TRUE),
            pct_negative      = mean(sentiment_label == "negative", na.rm = TRUE),
            pct_neutral       = mean(sentiment_label == "neutral",  na.rm = TRUE),
            .groups = "drop") %>%
  mutate(across(where(is.numeric), ~round(.x, 4)))
print(kable(desc_comments))
write_csv(desc_comments, file.path(RESULTS_DIR, "r_desc_comments.csv"))

cat("\n=== Descriptives: PR level ===\n")
desc_pr <- pr_level %>%
  group_by(repo_id, period) %>%
  summarise(n = n(),
            avg_thread_depth = mean(comment_count, na.rm = TRUE),
            avg_participants = mean(unique_authors, na.rm = TRUE),
            avg_pushpull_ratio = mean(pushpull_ratio, na.rm = TRUE),
            avg_pushpull_count = mean(pushpull_count, na.rm = TRUE),
            .groups = "drop") %>%
  mutate(across(where(is.numeric), ~round(.x, 4)))
print(kable(desc_pr))
write_csv(desc_pr, file.path(RESULTS_DIR, "r_desc_pr.csv"))

# By repo type (corporate vs community)
desc_type <- comments_prose %>%
  group_by(type, period) %>%
  summarise(n = n(),
            avg_word_count = mean(word_count, na.rm = TRUE),
            avg_lex_mtld   = mean(lexical_diversity, na.rm = TRUE),
            avg_question   = mean(question_ratio, na.rm = TRUE),
            avg_hedging    = mean(hedging_ratio, na.rm = TRUE),
            avg_polarity   = mean(polarity, na.rm = TRUE),
            .groups = "drop") %>%
  mutate(across(where(is.numeric), ~round(.x, 4)))
write_csv(desc_type, file.path(RESULTS_DIR, "r_desc_type.csv"))

# Pre-computed type summaries from Python (descriptive support)
dyn_type  <- read_csv(file.path(RESULTS_DIR, "dynamics_type_summary.csv"),
                      show_col_types = FALSE)
sent_type <- read_csv(file.path(RESULTS_DIR, "sentiment_type_summary.csv"),
                      show_col_types = FALSE)
cat("\n=== Dynamics by type (from Python) ===\n");  print(kable(dyn_type))
cat("\n=== Sentiment by type (from Python) ===\n"); print(kable(sent_type))

# 3. Inferential tests (Welch t-test + Cohen's d)
cohens_d_manual <- function(x, y) {
  x <- na.omit(x); y <- na.omit(y)
  nx <- length(x); ny <- length(y)
  if (nx < 2 || ny < 2) return(NA_real_)
  pooled_sd <- sqrt(((nx-1)*var(x) + (ny-1)*var(y)) / (nx+ny-2))
  if (pooled_sd == 0) return(0)
  (mean(x) - mean(y)) / pooled_sd
}

magnitude_label <- function(d) {
  d <- abs(d)
  if (is.na(d))   return("NA")
  if (d < 0.2)    return("negligible")
  if (d < 0.5)    return("small")
  if (d < 0.8)    return("medium")
  "large"
}

run_ttest <- function(data, metric) {
  data %>%
    group_by(repo_id) %>%
    group_map(~ {
      pre  <- na.omit(.x %>% filter(period == "pre_ai")  %>% pull(!!sym(metric)))
      post <- na.omit(.x %>% filter(period == "post_ai") %>% pull(!!sym(metric)))
      if (length(pre) < 2 || length(post) < 2) return(NULL)
      tt <- t.test(pre, post, var.equal = FALSE)
      d  <- cohens_d_manual(pre, post)
      tibble(repo_id = as.character(.y$repo_id), metric = metric,
             pre_mean = round(mean(pre),4),  post_mean = round(mean(post),4),
             t_statistic = round(tt$statistic,4), df = round(tt$parameter,2),
             p_value = round(tt$p.value,4), cohens_d = round(d,4),
             magnitude = magnitude_label(d), significant = tt$p.value < 0.05,
             n_pre = length(pre), n_post = length(post))
    }, .keep = TRUE) %>% bind_rows()
}

cat("\n=== t-tests: comment-level metrics ===\n")
comment_metrics <- c("word_count","lexical_diversity",
                     "question_ratio","hedging_ratio","polarity")
ttest_comments <- map_dfr(comment_metrics, ~run_ttest(comments_prose, .x))
print(kable(ttest_comments))
write_csv(ttest_comments, file.path(RESULTS_DIR, "r_ttest_comments.csv"))

cat("\n=== t-tests: PR-level metrics ===\n")
pr_metrics <- c("comment_count","unique_authors",
                "pushpull_ratio","pushpull_count")
ttest_pr <- map_dfr(pr_metrics, ~run_ttest(pr_level, .x))
print(kable(ttest_pr))
write_csv(ttest_pr, file.path(RESULTS_DIR, "r_ttest_pr.csv"))

# Multiple-comparison correction across all t-tests (BH)
all_ttests <- bind_rows(ttest_comments, ttest_pr) %>%
  mutate(p_adjusted  = round(p.adjust(p_value, method = "BH"), 4),
         sig_adjusted = p_adjusted < 0.05)
write_csv(all_ttests, file.path(RESULTS_DIR, "r_ttest_all_adjusted.csv"))

# Chi-square: sentiment label distribution (prose only)
cat("\n=== Chi-square: sentiment distribution ===\n")
chi_results <- comments_prose %>%
  group_by(repo_id) %>%
  group_map(~ {
    tab <- table(.x$period, .x$sentiment_label)
    if (any(dim(tab) < 2)) return(NULL)
    ch <- chisq.test(tab)
    tibble(repo_id = as.character(.y$repo_id),
           chi_squared = round(ch$statistic,4), df = ch$parameter,
           p_value = round(ch$p.value,4), significant = ch$p.value < 0.05)
  }, .keep = TRUE) %>% bind_rows()
print(kable(chi_results))
write_csv(chi_results, file.path(RESULTS_DIR, "r_chisquare.csv"))

# Robustness: strict vs heuristic question detection
cat("\n=== Question-ratio robustness (strict vs heuristic) ===\n")

# Descriptive means under both definitions
q_means <- comments_prose %>%
  group_by(repo_id, period) %>%
  summarise(strict_mean = round(mean(question_ratio,      na.rm = TRUE), 4),
            heur_mean   = round(mean(question_ratio_heur, na.rm = TRUE), 4),
            .groups = "drop")
print(kable(q_means, caption = "Question ratio: group means under both definitions"))

# Actual robustness check: running the identical Welch t-test on each definition,
# then compare direction and significance per repository.
cat("\n=== Question-ratio robustness (strict vs heuristic) ===\n")

# Descriptive means under both definitions (your existing table)
q_means <- comments_prose %>%
  group_by(repo_id, period) %>%
  summarise(strict_mean = round(mean(question_ratio,      na.rm = TRUE), 4),
            heur_mean   = round(mean(question_ratio_heur, na.rm = TRUE), 4),
            .groups = "drop")
print(kable(q_means, caption = "Question ratio: group means under both definitions"))

# identical Welch t-test on each definition,
# with the same multiple-comparison correction used for the main results,
# applied within each definition's four repositories.
q_strict <- run_ttest(comments_prose, "question_ratio") %>%
  mutate(p_adj   = p.adjust(p_value, method = "holm"),
         sig_adj = p_adj < 0.05)

q_heur <- run_ttest(comments_prose, "question_ratio_heur") %>%
  mutate(p_adj   = p.adjust(p_value, method = "holm"),
         sig_adj = p_adj < 0.05)

q_robust <- q_strict %>%
  select(repo_id,
         strict_pre = pre_mean, strict_post = post_mean,
         strict_d   = cohens_d, strict_sig  = sig_adj) %>%
  left_join(
    q_heur %>%
      select(repo_id,
             heur_pre = pre_mean, heur_post = post_mean,
             heur_d   = cohens_d, heur_sig  = sig_adj),
    by = "repo_id"
  ) %>%
  mutate(
    strict_dir       = if_else(strict_post < strict_pre, "down", "up"),
    heur_dir         = if_else(heur_post   < heur_pre,   "down", "up"),
    direction_agrees = strict_dir == heur_dir,
    sig_agrees       = strict_sig  == heur_sig
  )

print(kable(q_robust, caption = "Robustness: strict vs heuristic question ratio (adjusted)"))
write_csv(q_robust, file.path(RESULTS_DIR, "r_question_robustness.csv"))

cat(sprintf("Question-ratio robustness: direction agrees in %d/4 repos, significance agrees in %d/4.\n",
            sum(q_robust$direction_agrees),
            sum(q_robust$sig_agrees)))

# 4. Mixed-effects models (repo as random effect)
run_mixed <- function(data, outcome) {
  f <- as.formula(paste0(outcome, " ~ period + (1 | repo_id)"))
  lmer(f, data = data, REML = FALSE,
       control = lmerControl(optimizer = "bobyqa"))
}

# lexical_diversity has NA (short comments) — dropped before fitting
comments_lex <- comments_prose %>% filter(!is.na(lexical_diversity))

models <- list(
  "Thread Depth"      = run_mixed(pr_level,       "comment_count"),
  "Participants"      = run_mixed(pr_level,       "unique_authors"),
  "Push-Pull Ratio"   = run_mixed(pr_level,       "pushpull_ratio"),
  "Push-Pull Count"   = run_mixed(pr_level,       "pushpull_count"),
  "Word Count"        = run_mixed(comments_prose, "word_count"),
  "Lexical Diversity" = run_mixed(comments_lex,   "lexical_diversity"),
  "Question Ratio"    = run_mixed(comments_prose, "question_ratio"),
  "Hedging Ratio"     = run_mixed(comments_prose, "hedging_ratio"),
  "Polarity"          = run_mixed(comments_prose, "polarity")
)

extract_coef <- function(model, label) {
  tidy(model, effects = "fixed", conf.int = TRUE) %>%
    filter(term == "periodpost_ai") %>%
    transmute(outcome = label,
              estimate = round(estimate,4), std.error = round(std.error,4),
              statistic = round(statistic,4), p.value = round(p.value,4),
              conf.low = round(conf.low,4), conf.high = round(conf.high,4),
              significant = p.value < 0.05)
}

regression_table <- imap_dfr(models, ~extract_coef(.x, .y))
cat("\n=== Regression summary (post_ai coefficient) ===\n")
print(kable(regression_table))
write_csv(regression_table, file.path(RESULTS_DIR, "r_regression_table.csv"))

# Interaction: does the AI effect differ by repo type?
cat("\n=== Interaction model: thread depth ~ period * type ===\n")
m_interaction <- lmer(comment_count ~ period * type + (1 | repo_id),
                      data = pr_level, REML = FALSE,
                      control = lmerControl(optimizer = "bobyqa"))
print(summary(m_interaction))
tidy(m_interaction, effects = "fixed", conf.int = TRUE) %>%
  mutate(across(where(is.numeric), ~round(.x, 4))) %>%
  write_csv(file.path(RESULTS_DIR, "r_interaction_model.csv"))

# 5. Figures

## 5a. Forest plot, auto-binned by coefficient magnitude
regression_plot <- regression_table %>%
  mutate(scale_group = ifelse(abs(estimate) >= 1, "Large scale", "Small scale"))

p_forest <- ggplot(regression_plot,
                   aes(estimate, reorder(outcome, estimate), colour = significant)) +
  geom_vline(xintercept = 0, linetype = "dashed", colour = "grey50") +
  geom_errorbar(aes(xmin = conf.low, xmax = conf.high),
                width = 0.2, orientation = "y") +
  geom_point(size = 3) +
  facet_wrap(~scale_group, scales = "free") +
  scale_colour_manual(values = c("TRUE"="#C96A50","FALSE"="#5B8DB8"),
                      labels = c("TRUE"="p < 0.05","FALSE"="p ≥ 0.05")) +
  labs(title = "Effect of AI Adoption on Communication Metrics",
       subtitle = "Mixed-effects regression coefficients (post_ai vs pre_ai)",
       x = "Estimated Change Post-AI (β)", y = NULL, colour = "Significance") +
  theme_pubr() + theme(legend.position = "bottom")
ggsave(file.path(RESULTS_DIR,"plots","forest_plot.png"),
       p_forest, width = 11, height = 6, dpi = 300)

## 5b. Thread depth (capped at 60 for readability)
p_depth <- ggplot(pr_level, aes(period, comment_count, fill = period)) +
  geom_boxplot(outlier.shape = NA, alpha = .8, width = .5) +
  geom_jitter(width = .15, alpha = .06, size = .6, colour = "grey40") +
  facet_wrap(~repo_id, scales = "free_y") +
  coord_cartesian(ylim = c(0, 60)) +
  scale_fill_manual(values = PALETTE, labels = LABELS) +
  scale_x_discrete(labels = LABELS) +
  labs(title = "Thread Depth: Pre vs Post AI Adoption",
       subtitle = "Comments per PR (outliers above 60 not shown)",
       x = NULL, y = "Comments per PR", fill = "Period") +
  theme_pubr() + theme(legend.position = "bottom")
ggsave(file.path(RESULTS_DIR,"plots","thread_depth.png"),
       p_depth, width = 10, height = 6, dpi = 300)

## 5c. Push-pull ratio with significance markers
p_pp <- ggplot(pr_level, aes(period, pushpull_ratio, fill = period)) +
  geom_boxplot(outlier.shape = NA, alpha = .8) +
  stat_compare_means(comparisons = list(c("pre_ai","post_ai")),
                     method = "t.test", label = "p.signif", size = 3) +
  facet_wrap(~repo_id) +
  scale_fill_manual(values = PALETTE, labels = LABELS) +
  scale_x_discrete(labels = LABELS) +
  labs(title = "Push-Pull Ratio: Pre vs Post AI Adoption",
       subtitle = "Proportion of consecutive comments by different authors",
       x = NULL, y = "Push-Pull Ratio (0-1)", fill = "Period") +
  theme_pubr() + theme(legend.position = "bottom")
ggsave(file.path(RESULTS_DIR,"plots","pushpull_ratio.png"),
       p_pp, width = 10, height = 6, dpi = 300)

## 5d. Word count (capped at 300)
p_words <- comments_prose %>%
  mutate(wc = pmin(word_count, 300)) %>%
  ggplot(aes(period, wc, fill = period)) +
  geom_boxplot(outlier.shape = NA, alpha = .8) +
  facet_wrap(~repo_id, nrow = 1) +
  scale_fill_manual(values = PALETTE, labels = LABELS) +
  scale_x_discrete(labels = LABELS) +
  labs(title = "Comment Length: Pre vs Post AI Adoption",
       subtitle = "Word count per comment (capped at 300)",
       x = NULL, y = "Words per Comment", fill = "Period") +
  theme_pubr() + theme(legend.position = "bottom")
ggsave(file.path(RESULTS_DIR,"plots","word_count.png"),
       p_words, width = 12, height = 4, dpi = 300)

## 5e. Linguistic ratios; question + hedging only (shared 0-1 axis)
ratios_long <- comments_prose %>%
  select(repo_id, period, question_ratio, hedging_ratio) %>%
  pivot_longer(c(question_ratio, hedging_ratio),
               names_to = "metric", values_to = "value") %>%
  mutate(metric = recode(metric,
           question_ratio = "Question Ratio",
           hedging_ratio  = "Hedging Ratio"))

p_ratios <- ggplot(ratios_long, aes(period, value, fill = period)) +
  geom_boxplot(outlier.shape = NA, alpha = .8) +
  facet_grid(metric ~ repo_id, scales = "free_y") +
  scale_fill_manual(values = PALETTE, labels = LABELS) +
  scale_x_discrete(labels = LABELS) +
  labs(title = "Linguistic Ratios: Pre vs Post AI Adoption",
       subtitle = "Hedging values are small by nature (~0.02-0.04) in technical review",
       x = NULL, y = "Ratio (0-1)", fill = "Period") +
  theme_pubr(base_size = 10) +
  theme(legend.position = "bottom",
        axis.text.x = element_text(angle = 30, hjust = 1))
ggsave(file.path(RESULTS_DIR,"plots","linguistic_ratios.png"),
       p_ratios, width = 12, height = 7, dpi = 300)

## 5f. Lexical diversity (MTLD), its own scale, NA dropped
p_lex <- comments_prose %>%
  filter(!is.na(lexical_diversity)) %>%
  ggplot(aes(period, lexical_diversity, fill = period)) +
  geom_boxplot(outlier.shape = NA, alpha = .8) +
  facet_wrap(~repo_id, nrow = 1) +
  scale_fill_manual(values = PALETTE, labels = LABELS) +
  scale_x_discrete(labels = LABELS) +
  labs(title = "Lexical Diversity (MTLD): Pre vs Post AI Adoption",
       subtitle = "Length-robust measure; comments under 10 words excluded",
       x = NULL, y = "MTLD", fill = "Period") +
  theme_pubr() + theme(legend.position = "bottom")
ggsave(file.path(RESULTS_DIR,"plots","lexical_diversity.png"),
       p_lex, width = 12, height = 4, dpi = 300)

## 5g. Sentiment — negative proportion with 95% CI (primary figure)
sent_props <- comments_prose %>%
  group_by(repo_id, period) %>%
  summarise(n = n(), n_neg = sum(sentiment_label == "negative"),
            prop = n_neg / n,
            ci_low  = prop.test(n_neg, n)$conf.int[1],
            ci_high = prop.test(n_neg, n)$conf.int[2],
            .groups = "drop")

p_sent <- ggplot(sent_props, aes(period, prop, colour = period, group = repo_id)) +
  geom_line(colour = "grey70", linewidth = .5) +
  geom_errorbar(aes(ymin = ci_low, ymax = ci_high), width = .1) +
  geom_point(size = 4) +
  facet_wrap(~repo_id, nrow = 1) +
  scale_colour_manual(values = PALETTE, labels = LABELS, name = "Period") +
  scale_x_discrete(labels = LABELS) +
  scale_y_continuous(labels = percent_format(accuracy = 1), limits = c(0, .25)) +
  labs(title = "Proportion of Negative Comments: Pre vs Post AI Adoption",
       subtitle = "SentiCR (prose only) — error bars are 95% CIs",
       caption = "Note: under 1% of comments classified positive in any repo or period",
       x = NULL, y = "Proportion of Negative Comments") +
  theme_pubr() + theme(legend.position = "bottom",
                       strip.text = element_text(size = 9))
ggsave(file.path(RESULTS_DIR,"plots","sentiment_negative_prop.png"),
       p_sent, width = 12, height = 5, dpi = 300)

## 5h. Sentiment stacked distribution - add-on
sent_dist <- comments_prose %>%
  group_by(repo_id, period, sentiment_label) %>%
  summarise(n = n(), .groups = "drop") %>%
  group_by(repo_id, period) %>% mutate(pct = n / sum(n))

p_sent_stack <- ggplot(sent_dist, aes(period, pct, fill = sentiment_label)) +
  geom_col(position = "stack") +
  facet_wrap(~repo_id) +
  scale_fill_manual(values = c(positive="#5B8DB8", neutral="#B8B8B8", negative="#C96A50")) +
  scale_x_discrete(labels = LABELS) +
  scale_y_continuous(labels = percent_format()) +
  labs(title = "Sentiment Distribution: Pre vs Post AI Adoption",
       subtitle = "SentiCR classification of prose comments",
       x = NULL, y = "Proportion of Comments", fill = "Sentiment") +
  theme_pubr() + theme(legend.position = "bottom")
ggsave(file.path(RESULTS_DIR,"plots","sentiment_distribution.png"),
       p_sent_stack, width = 10, height = 6, dpi = 300)

cat("\n=== Analysis complete. Tables and plots written to results/ ===\n")