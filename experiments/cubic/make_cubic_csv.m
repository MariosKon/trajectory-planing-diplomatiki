%% Fixed-time cubic Cartesian ServoP experiment (standalone script)
% Writes 3 CSVs: T=3.93, 2.79, 2.31 s (30 ms sample period).
% Uses exact same start/end TCP poses as the final MoveL experiment.
% MATLAB: run('experiments/cubic/make_cubic_csv.m')
% Open 3 diagnostic figures (position, velocity, acceleration, jerk).
% Set makePlot=false only when you deliberately want a non-graphical export.

here = fileparts(mfilename('fullpath'));
addpath(fullfile(here, '..', 'polynomial_fixed_time'));
makePlot = true;
generate_fixed_time_polynomial('cubic', here, makePlot);
