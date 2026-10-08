%% make_cubic_csv.m
% Standalone cubic-polynomial trajectory CSV generator
% -----------------------------------------------------
% This script DOES NOT read any input CSV.
%
% You define:
%   - start pose
%   - end pose
%   - maximum velocity
%   - maximum acceleration
%   - fixed sample time
%
% It generates:
%   mode,x1,x2,x3,x4,x5,x6
%
% The trajectory is sampled every 30 ms.
%
% Cubic polynomial boundary conditions:
%   q(0) = qStart
%   q(T) = qEnd
%   qdot(0) = 0
%   qdot(T) = 0
%
% Normalized cubic:
%   s(tau) = 3*tau^2 - 2*tau^3
%   tau = t/T

clear;
clc;

%% ================= USER SETTINGS =================

outputCsv = 'points_cubic.csv';

Ts = 0.030;   % [s] fixed time between consecutive points

% Start and end pose
qStart = [-600, -400, 250, -90, 0, 90];
qEnd   = [-600,  400, 250, -90, 0, 90];

% Motion limits
vMax = 600;    % [units/s]
aMax = 2000;   % [units/s^2]

% Text written in the first CSV column
mode = 'ServoP';

makePlot = true;

%% =================================================

delta = qEnd - qStart;

if all(abs(delta) < 1e-12)
    error('Start and end poses are identical.');
end

% Use the coordinate with the largest displacement to determine duration.
[distance, driverAxis] = max(abs(delta));

%% Calculate minimum cubic duration

% For s = 3*tau^2 - 2*tau^3:
%
% maximum normalized velocity:
%   max(ds/dt) = 1.5 / T
%
% maximum normalized acceleration:
%   max(abs(d2s/dt2)) = 6 / T^2
%
% Therefore:
%   T >= 1.5*D/vMax
%   T >= sqrt(6*D/aMax)

TfromV = 1.5 * distance / vMax;
TfromA = sqrt(6 * distance / aMax);

Tmin = max(TfromV, TfromA);

%% Align total duration to exact 30 ms grid

nIntervals = ceil(Tmin / Ts - 1e-12);
Tfinal = nIntervals * Ts;

%% Generate samples

t = (0:nIntervals).' * Ts;

tau = t / Tfinal;

% Cubic normalized position
s = 3*tau.^2 - 2*tau.^3;

% Normalized velocity
sd = (6*tau - 6*tau.^2) / Tfinal;

% Normalized acceleration
sdd = (6 - 12*tau) / Tfinal^2;

% Normalized jerk
sddd = (-12 / Tfinal^3) * ones(size(t));

% Force exact boundary values
s(1)   = 0;
s(end) = 1;

sd(1)   = 0;
sd(end) = 0;

%% Generate all six coordinates

Q = bsxfun(@plus, qStart, bsxfun(@times, s, delta));

Q(1,:)   = qStart;
Q(end,:) = qEnd;

%% Driver-axis derivatives for verification

direction = sign(delta(driverAxis));

vPath = direction * distance * sd;
aPath = direction * distance * sdd;
jPath = direction * distance * sddd;

%% Create CSV table

N = numel(t);

modeColumn = repmat({mode}, N, 1);

T = table( ...
    modeColumn, ...
    Q(:,1), Q(:,2), Q(:,3), ...
    Q(:,4), Q(:,5), Q(:,6), ...
    'VariableNames', ...
    {'mode','x1','x2','x3','x4','x5','x6'});

writetable(T, outputCsv);

%% Information

fprintf('\nCSV generated successfully.\n');
fprintf('File: %s\n', outputCsv);
fprintf('Profile: cubic polynomial\n');
fprintf('Number of points: %d\n', N);
fprintf('Sample time: %.3f s\n', Ts);
fprintf('Motion duration: %.3f s\n', Tfinal);
fprintf('Driver coordinate: x%d\n', driverAxis);
fprintf('Maximum displacement: %.3f\n', distance);

fprintf('\nDuration requirements:\n');
fprintf('From velocity limit:     %.6f s\n', TfromV);
fprintf('From acceleration limit: %.6f s\n', TfromA);
fprintf('Continuous minimum:      %.6f s\n', Tmin);
fprintf('Grid-aligned duration:   %.6f s\n', Tfinal);

fprintf('\nPeak values:\n');
fprintf('Velocity:     %.3f\n', max(abs(vPath)));
fprintf('Acceleration: %.3f\n', max(abs(aPath)));
fprintf('Jerk:         %.3f\n', max(abs(jPath)));

%% Plot for verification

if makePlot
    figure('Name','Cubic polynomial trajectory');

    subplot(4,1,1)
    plot(t, Q(:,driverAxis), 'LineWidth', 1.3);
    grid on;
    ylabel(sprintf('x%d',driverAxis));
    title('Cubic polynomial trajectory');

    subplot(4,1,2)
    plot(t, vPath, 'LineWidth', 1.3);
    grid on;
    ylabel('Velocity');

    subplot(4,1,3)
    plot(t, aPath, 'LineWidth', 1.3);
    grid on;
    ylabel('Acceleration');

    subplot(4,1,4)
    plot(t, jPath, 'LineWidth', 1.3);
    grid on;
    ylabel('Jerk');
    xlabel('Time [s]');
end
