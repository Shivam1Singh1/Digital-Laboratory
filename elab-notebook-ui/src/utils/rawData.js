/**
 * Visibility rules for the Lab Experiment "Raw Data" tab.
 *
 * Each function mirrors one `depends_on` expression on the doctype, and the
 * expression it mirrors is quoted above it. The doctype is the authority: these
 * exist so the SPA hides the same things the desk form hides, and so the two
 * forms in this app cannot drift apart from each other either. A field the SPA
 * shows but the server refuses is a save-time surprise; a field the SPA hides
 * but the server requires is worse.
 */

// attachments_tab -> eval:doc.experiment_category != "Master Experiment"
//
// An exclusion, not a list of the three levels below Master: a run with no
// category yet - this site has six - would drop off an allow-list, and so would
// any level added later.
export const showsRawDataTab = (category) => category !== 'Master Experiment'

// nature_of_sample -> eval: ["Sub Experiment", "Experiment"].includes(doc.experiment_category)
//
// Narrower than the tab: a Sub Sub Experiment carries raw data but names no
// nature of sample.
export const showsNatureOfSample = (category) =>
  ['Sub Experiment', 'Experiment'].includes(category)

// quality_metrics -> eval:doc.nature_of_sample
//
// Keyed on the field, not on the category. The two coincide in practice only
// because nature_of_sample can be set on those same two levels - reading this
// as "Experiment and Sub Experiment" would still leave the grid showing on a
// run whose nature_of_sample was cleared.
export const showsQualityMetrics = (natureOfSample) => Boolean(natureOfSample)
