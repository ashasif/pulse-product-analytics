# Phase 5 — Experimentation & Statistical Inference Contract

Status: COMPLETE & CLOSED

## 1. Purpose

Phase 5 extends the descriptive experiment analysis produced in Phase 4 into
a controlled statistical-inference layer for Pulse's randomized experiments.

The purpose is not to manufacture statistical significance or add statistical
tests for their own sake.

The Phase 5 analysis must answer:

1. What population is being analysed?
2. What estimand is being reported?
3. What uncertainty surrounds the observed effect?
4. Is the observed difference practically meaningful?
5. Is the evidence compatible with random variation?
6. Are maturity, randomization, lineage and metric-definition controls intact?
7. What decision, if any, is justified by the evidence?

Pulse is synthetic and must remain clearly disclosed as synthetic.

---

## 2. Architectural source of truth

Phase 5 business-facing analysis must consume the validated reporting semantic
layer.

Permitted business sources include:

- `reporting.metric_definitions`
- `reporting.vw_experiment_assignment_outcomes`
- `reporting.vw_experiment_variant_summary`
- `reporting.vw_observation_cutoff`
- other validated `reporting.*` objects only when genuinely required

Phase 5 must not bypass the reporting layer by querying directly from:

- `raw.*`
- `staging.*`
- `validation.*`
- `analytics.*`

Database access must remain read-only.

Where database access is required, Phase 5 should reuse:

- `src/analysis/reporting_client.py`
- `src/ingestion/database.py` where appropriate

Python must not redefine canonical KPI formulas that already belong to the
reporting semantic layer.

---

## 3. Existing experiment design

Pulse currently contains three randomized synthetic product experiments:

1. Paywall Redesign Experiment
2. Onboarding Guidance Experiment
3. AI Assistant Discovery Experiment

Randomization unit:

`user`

Experiment assignments were generated independently of downstream outcomes.

Experiment generation does not rewrite existing lifecycle, usage or
subscription outcomes.

Therefore Phase 5 must not assume that treatment effects were deliberately
embedded into the synthetic generator.

Observed control-versus-treatment differences may simply reflect sampling
variation.

That property is useful: the inference layer must be capable of concluding
that evidence is weak or consistent with no material effect.

---

## 4. Primary estimand

The primary experiment population is:

`assigned_mature`

This means:

- retain the original randomized assignment;
- require the relevant analysis window to be mature at the approved
  observation cutoff;
- analyse outcomes according to assigned variant;
- preserve control versus treatment allocation;
- do not condition the primary estimand on downstream behaviour.

This is an intention-to-treat-style randomized-assignment estimand.

Administrative maturity filtering is allowed because maturity is determined
by assignment timing, the predefined analysis window and the approved
observation cutoff rather than by observed treatment success.

Immature analysis windows must never enter primary inference denominators.

---

## 5. Exposure-conditioned populations

An exposed-only population may be useful as a supplementary diagnostic.

It is not the default primary causal estimand.

Exposure happens after assignment and can depend on post-randomization user
behaviour. Conditioning on exposure can therefore compromise the protection
provided by randomization.

Any exposed-only result must be explicitly labelled:

`supplementary / exposure-conditioned`

It must not silently replace the assigned-mature primary result.

---

## 6. Metric roles

Each experiment can contain:

- primary metric
- secondary metric
- commercial metric
- guardrail metric

Metric role and statistical outcome type are separate concepts.

Supported statistical outcome types for Phase 5 are initially:

- binary
- continuous
- count

Statistical type metadata describes how an existing outcome is analysed.

It must not redefine the business meaning or calculation of the metric.

---

## 7. Binary outcomes

Binary experiment outcomes are analysed as differences in proportions.

Required reporting includes:

- control numerator
- control denominator
- treatment numerator
- treatment denominator
- control rate
- treatment rate
- absolute percentage-point effect
- relative effect where the control rate is non-zero
- confidence interval for the absolute effect
- hypothesis-test result
- raw p-value
- adjusted p-value when multiplicity control applies

Phase 5 must not report a p-value without the corresponding effect size and
uncertainty interval.

---

## 8. Continuous and count outcomes

Continuous and count metrics require an explicit justification before
inferential testing.

The default estimand is the difference in group means when the business
metric itself is mean-based.

Before selecting a method, Phase 5 must inspect:

- group sample sizes
- distribution shape
- concentration at zero
- extreme skew
- influential values
- variance imbalance
- whether the metric is genuinely continuous or count-valued

A method must not be selected solely because it is available in a Python
library.

Where large-sample mean inference is justified, a heteroskedasticity-tolerant
two-sample method may be used.

Where assumptions are materially unsuitable, a bootstrap or another justified
method may be introduced explicitly.

---

## 9. Confidence level and alpha

Default significance level:

`alpha = 0.05`

Default confidence level:

`95%`

These values are methodological defaults, not evidence thresholds that turn
business decisions into automatic yes/no rules.

---

## 10. Multiplicity

Each experiment has multiple reported outcomes.

The primary metric is the single prespecified principal outcome.

Secondary, commercial and guardrail metrics are supportive outcomes.

Phase 5 will use Holm multiplicity adjustment for the supportive metric family
within an experiment when inferential claims across multiple supportive
outcomes are reported together.

Both raw and adjusted p-values may be retained for auditability.

Multiplicity adjustment must not be used to disguise which metric was
prespecified as primary.

---

## 11. Statistical versus practical significance

A statistically detectable difference is not automatically commercially or
product-relevant.

Every experiment conclusion must consider:

- absolute effect
- relative effect where meaningful
- confidence interval
- baseline rate or mean
- sample size
- minimum detectable effect / design sensitivity
- business context
- guardrail behaviour

Phase 5 must avoid binary language such as:

`the experiment worked`

solely because a p-value crossed 0.05.

---

## 12. Power and minimum detectable effect

Phase 5 may calculate prospective or design-based sensitivity diagnostics.

Minimum detectable effect is preferred to retrospective "observed power".

Phase 5 must not use post-hoc observed power as evidence supporting or
rejecting an experiment result.

---

## 13. Causal interpretation

Randomized assignment provides a legitimate basis for causal interpretation
of the assigned-mature treatment contrast when:

- randomization integrity is preserved;
- treatment assignment precedes outcomes;
- maturity rules are outcome-independent;
- material sample-ratio anomalies are absent;
- no post-randomization selection is introduced into the primary population;
- metric construction is valid;
- analysis follows the prespecified experiment design.

Causal interpretation applies to the randomized assignment contrast, not
automatically to arbitrary post-treatment subsets.

Because Pulse is synthetic and treatment assignments do not rewrite downstream
outcomes, Phase 5 must remain willing to conclude that observed differences are
consistent with random variation.

---

## 14. Sample-ratio checks

Before inferential conclusions, each experiment must compare observed variant
allocation against configured randomization allocation.

Material sample-ratio mismatch must be surfaced as an experiment-integrity
warning.

A statistical result must not silently proceed as decision-quality evidence
when randomization integrity is questionable.

---

## 15. Lineage

All Phase 5 outputs must preserve production lineage wherever available.

Current approved production lineage:

- ingestion batch: `1`
- validation run: `1`
- promotion run: `1`
- analytics build run: `1`

Approved reporting observation cutoff:

`2026-07-01T00:59:36+01:00`

Analysis rows from incompatible production lineage must not be combined.

---

## 16. Phase 5 outputs

Phase 5 outputs will eventually include:

- experiment-level inference results
- uncertainty intervals
- multiplicity-controlled evidence
- randomization-integrity diagnostics
- minimum-detectable-effect diagnostics
- machine-readable validation evidence
- portfolio-quality experiment summaries

Outputs must remain reproducible.

---

## 17. Phase 5 exclusions

Phase 5 does not include:

- predictive machine learning
- churn modelling
- recommendation models
- uplift modelling
- propensity-score modelling
- generic observational causal inference
- forecasting
- Streamlit
- dashboard construction
- Bayesian experimentation
- accounting revenue recognition
- LTV invention
- unsupported KPI invention
- modification of `data/raw/`
- rewriting Phase 4 descriptive outputs

These capabilities require their own architectural justification if considered
later.

---

## 18. Relationship to Phase 4

Phase 4 remains complete and closed.

Phase 4 experiment reporting is descriptive.

Phase 5 adds a separate inferential methodology and must not retrospectively
relabel Phase 4 descriptive differences as causal or statistically
significant.

If Phase 5 discovers a genuine upstream defect, the defect must be documented
explicitly before any completed Phase 3 or Phase 4 contract is changed.

---

## 19. Implementation principle

The sequence is:

1. validate design and analysis population;
2. validate lineage and maturity;
3. validate randomization integrity;
4. classify statistical outcome type;
5. calculate effect;
6. quantify uncertainty;
7. evaluate statistical evidence;
8. evaluate multiplicity;
9. evaluate practical significance;
10. produce a restrained decision interpretation.

No statistical conclusion may skip the controls that precede it.

---

## 20. Operational sample-ratio mismatch rule

Pulse Phase 5 uses a two-arm sample-ratio-mismatch diagnostic before
outcome-level inferential conclusions.

The expected sample ratio comes from each experiment's configured allocation.
It must never be assumed to be universally 50/50.

Default SRM threshold:

`alpha = 0.001`

This stricter diagnostic threshold is separate from the outcome-inference
default alpha of 0.05.

For the current two-arm experiments, Pearson's chi-square allocation test with
one degree of freedom is used.

A detected SRM is treated as an experiment-integrity warning. Outcome results
may still be calculated for diagnosis, but they must not be presented as
decision-quality causal evidence until the allocation anomaly is explained.

SRM must be evaluated on the randomized assignment population. The
assigned-mature population must also preserve the expected ratio before it is
used for primary inference.

---

## 21. Binary outcome implementation method

Phase 5 binary experiment metrics use the randomized assigned-mature
population.

Effect direction is always:

`treatment - control`

For every binary metric Phase 5 reports:

- control successes and denominator;
- treatment successes and denominator;
- control proportion;
- treatment proportion;
- absolute treatment-minus-control effect;
- percentage-point effect;
- relative effect when the control proportion is non-zero;
- uncertainty interval for the absolute effect;
- two-sided hypothesis-test p-value.

### Confidence interval

The confidence interval for the absolute difference in proportions uses a
Newcombe score interval constructed from Wilson intervals for the two
independent group proportions.

The basic unpooled Wald interval is not used as the default because of its
poorer finite-sample behaviour, particularly for proportions near zero or one.

Default confidence level:

`95%`

### Hypothesis test

The null hypothesis for the two-sided binary test is:

`H0: p_treatment - p_control = 0`

The hypothesis-test statistic uses the pooled two-proportion standard error
under the null.

The p-value is not reported without the treatment effect and confidence
interval.

### Relative effects

Relative effect is calculated only when the control rate is non-zero.

A zero control rate must not be converted into an infinite or invented
percentage uplift.

### Multiplicity

The experiment's prespecified primary metric remains identifiable as primary.

When secondary, commercial and guardrail metrics form a supportive inferential
family, Phase 5 applies Holm adjustment to their p-values.

Raw and adjusted p-values remain distinguishable.

A multiplicity adjustment must not convert an exploratory/supportive outcome
into the prespecified primary outcome.

### Interpretation

`p < 0.05` is not synonymous with business success.

The final experiment interpretation must consider:

- effect direction;
- absolute magnitude;
- confidence interval;
- baseline rate;
- multiplicity where applicable;
- experiment integrity;
- minimum detectable effect;
- guardrail behaviour;
- business relevance.

A confidence interval containing zero means the data do not provide a
sufficiently precise non-zero effect estimate at the configured confidence
level. It does not prove exact equality between variants.

---

## 22. Live experiment semantic gating

Phase 5 does not assume that every metric named in experiment configuration is
already canonicalized for business reporting.

Before live inference every configured experiment metric must be classified
against `reporting.metric_definitions`.

Possible states include:

- supported;
- deferred;
- unsupported;
- unknown / absent from the canonical metric registry.

Deferred, unsupported and unknown metrics are not reconstructed in Python and
are not silently replaced with similar-looking metrics.

For supported binary metrics, Phase 5 may bind the canonical metric key to the
corresponding boolean outcome primitive already exposed by
`reporting.vw_experiment_assignment_outcomes`.

This binding is metadata, not a redefinition of the KPI.

The randomized primary population remains:

`assigned_mature`

Binary numerators and denominators are therefore calculated from mature
assigned rows in the reporting semantic view.

The current production observation cutoff has zero immature assignments across
all three experiments, but the implementation retains explicit maturity
filtering so this remains valid for later observation contexts.

The supported metric:

`revenue_per_assigned_user_30d`

is continuous and must not be processed by the binary inference engine.

Multiplicity adjustment is not finalized during the binary-only stage because
doing so before all supported inferential outcome types are available would
define an incomplete supportive metric family.

---

## 23. Continuous commercial outcome method

The currently supported configured continuous commercial outcome is:

`revenue_per_assigned_user_30d`

for the Paywall Redesign Experiment.

The business interpretation remains:

`successful billed payment collection per assigned user`

It is not accounting-recognised revenue, net revenue, profit or customer LTV.

### Observed production distribution

The assigned-mature user-level collection distribution is strongly
zero-inflated and discrete.

At the current production cutoff approximately eighty-nine percent of users in
each variant have zero successful collection within thirty days.

The observed support is:

- £0.00
- £11.99
- £99.99

Therefore the user-level distribution is not treated as Gaussian merely for
convenience.

### Estimand

The Phase 5 commercial estimand is:

`treatment mean - control mean`

across all randomized assigned-mature users.

Users with zero collection remain in the analysis population.

Conditioning only on users who generated revenue would be a post-randomization
selection and would change the business estimand.

### Confidence interval

The primary uncertainty interval is a reproducible non-parametric percentile
bootstrap confidence interval for the difference in arithmetic means.

Default bootstrap replicates:

`10,000`

### Hypothesis test

The primary hypothesis test is a two-sided randomization/permutation test.

Variant labels are permuted while preserving observed control and treatment
sample sizes.

The test therefore uses the randomized experiment design rather than assuming
normally distributed user-level collection.

Default permutation replicates:

`10,000`

A finite-simulation correction is applied so the Monte Carlo p-value cannot be
reported as exactly zero.

### Reproducibility

Resampling uses fixed deterministic seeds recorded in Phase 5 output metadata.

No NumPy, SciPy or statsmodels dependency is required for this method.

### Interpretation

The bootstrap confidence interval quantifies uncertainty around the mean
collection difference.

The permutation p-value evaluates whether an effect at least as extreme as the
observed mean difference is unusual under randomized reassignment of treatment
labels.

Neither quantity converts statistical detectability automatically into a
commercial rollout decision.

---

## 24. Multiplicity and design sensitivity

### Multiplicity

The prespecified primary metric is evaluated separately.

Completed secondary, commercial and guardrail outcomes within the same
experiment form the supportive inferential family.

Holm family-wise error-rate adjustment is applied across that completed
supportive family.

Deferred, unsupported and unknown metric contracts are not assigned invented
p-values and therefore cannot be included in a completed inferential family.

### Minimum detectable effect

Phase 5 reports approximate minimum detectable effect diagnostics using:

- two-sided alpha = 0.05;
- target power = 0.80.

Binary MDE uses a local normal approximation around the observed control
baseline and actual control/treatment sample sizes.

A binary baseline at exactly zero or one is treated as saturated and an MDE is
not reported from this approximation.

Continuous mean MDE uses the observed arm-specific sample standard deviations
and actual control/treatment sample sizes.

These values describe experiment design sensitivity.

Phase 5 does not calculate retrospective observed power.

An observed effect smaller than the approximate MDE should be interpreted as
an effect magnitude that the current design was not well-powered to detect
reliably, not as proof that the effect is exactly zero.

---

## 25. Final experiment decision synthesis

Phase 5 experiment decisions combine:

- semantic-contract eligibility;
- randomized-assignment integrity;
- maturity control;
- effect magnitude;
- uncertainty interval;
- raw statistical evidence;
- supportive Holm multiplicity adjustment;
- minimum detectable effect diagnostics;
- commercial and guardrail context.

A configured experiment whose primary metric is deferred, unsupported or
absent from the canonical reporting metric registry is not considered
decision-ready.

A non-significant primary result does not prove exact treatment-control
equivalence.

Where supporting metrics remain unavailable, the final interpretation must
explicitly state that the evidence family is incomplete.

Where the complete supported experiment family is available but contains no
statistically detectable outcomes, Phase 5 may state that the completed
canonical evidence does not support a treatment rollout at the current
snapshot.

This statement must not be rewritten as:

`the treatment has no effect`

or:

`control and treatment are the same`.

Phase 5 remains a synthetic randomized-experiment inference exercise.
