import createPlotlyComponent from "react-plotly.js/factory";
// @ts-expect-error - plotly.js-cartesian-dist-min has no type declarations
import Plotly from "plotly.js-cartesian-dist-min";

const Plot = createPlotlyComponent(Plotly);

export default Plot;
