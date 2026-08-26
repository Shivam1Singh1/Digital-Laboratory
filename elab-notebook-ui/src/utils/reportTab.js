/**
 * Which levels get a Report tab.
 *
 * Unlike utils/rawData.js, this mirrors no doctype rule - `result_tab` and the
 * report's own fields carry no depends_on. It is a product decision, kept here
 * rather than inline so the detail page and the create form cannot disagree
 * about which levels offer the tab.
 *
 * The report is a run plus everything beneath it. At Sub Sub Experiment there is
 * no "beneath" at all, and at Sub Experiment the roll-up is a single level deep
 * - in both cases the tab rendered a card describing the run the user already
 * had open. The two levels that own a programme are the two that get it.
 */
export const REPORT_CATEGORIES = ['Master Experiment', 'Experiment']

export const showsReportTab = (category) => REPORT_CATEGORIES.includes(category)
