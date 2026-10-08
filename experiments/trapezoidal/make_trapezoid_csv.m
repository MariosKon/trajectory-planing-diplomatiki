%% make_trapezoid_csv.m
% Standalone trapezoidal-velocity-profile CSV generator
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
% If the move is too short to reach vMax, the profile automatically becomes
% triangular instead of trapezoidal.

clear;
clc;

%% ================= USER SETTINGS =================

outputCsv = 'points_trapezoid.csv';

Ts = 0.030;   % [s] fixed time between consecutive points

% Start and end pose
qStart = [-600, -400, 250, -90, 0, 90];
qEnd   = [-600,  400, 250, -90, 0, 90];

% Motion limits
vMax = 500;    % [units/s]
aMax = 1500;   % [units/s^2]

% Text written in the first CSV column
mode = 'ServoP';

makePlot = true;

%% =================================================

delta = qEnd - qStart;

if all(abs(delta) < 1e-12)
    error('Start and end poses are identical.');
end

% Use the coordinate with the largest displacement as the path driver.
[distance, driverAxis] = max(abs(delta));

% Generate scalar normalized trajectory from 0 to 1.
[t, s, vPath, aPath, info] = ...
    trapezoidRestToRest(distance, vMax, aMax, Ts);

% Apply the same normalized progress to all six coordinates.
Q = bsxfun(@plus, qStart, bsxfun(@times, s, delta));

% Force exact endpoints.
Q(1,:)   = qStart;
Q(end,:) = qEnd;

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
fprintf('Profile type: %s\n', info.profileType);
fprintf('Number of points: %d\n', N);
fprintf('Sample time: %.3f s\n', Ts);
fprintf('Motion duration: %.3f s\n', t(end));
fprintf('Driver coordinate: x%d\n', driverAxis);
fprintf('Maximum displacement: %.3f\n', distance);

fprintf('\nPeak values after 30 ms alignment:\n');
fprintf('Velocity:     %.3f\n', max(abs(vPath)));
fprintf('Acceleration: %.3f\n', max(abs(aPath)));

fprintf('\nContinuous minimum duration: %.6f s\n', info.minimumTime);
fprintf('Final grid-aligned duration: %.6f s\n', info.finalTime);
fprintf('Acceleration time: %.6f s\n', info.tAccel);
fprintf('Cruise time:       %.6f s\n', info.tCruise);
fprintf('Deceleration time: %.6f s\n', info.tAccel);

%% Plot for verification

if makePlot
    figure('Name','Trapezoidal trajectory');

    subplot(3,1,1)
    plot(t, Q(:,driverAxis), 'LineWidth', 1.3);
    grid on;
    ylabel(sprintf('x%d',driverAxis));
    title('Trapezoidal velocity profile');

    subplot(3,1,2)
    plot(t, vPath, 'LineWidth', 1.3);
    grid on;
    ylabel('Velocity');

    subplot(3,1,3)
    stairs(t, aPath, 'LineWidth', 1.3);
    grid on;
    ylabel('Acceleration');
    xlabel('Time [s]');
end


%% ============================================================
function [t, s, v, a, info] = ...
    trapezoidRestToRest(D, vMax, aMax, Ts)
% Symmetric rest-to-rest trapezoidal velocity profile.
%
% Phases:
%
%     +aMax  ->  0  ->  -aMax
%    accel      cruise     decel
%
% If the move is too short to reach vMax, the cruise phase disappears and
% the result is a triangular velocity profile.
%
% The minimum-time continuous profile is calculated first. Its total time
% is then rounded UP to an exact multiple of Ts and the entire profile is
% uniformly time-scaled. Therefore the generated samples are exactly Ts
% apart and the requested vMax/aMax limits are not exceeded.

validateattributes(D,    {'double'}, {'scalar','positive'});
validateattributes(vMax, {'double'}, {'scalar','positive'});
validateattributes(aMax, {'double'}, {'scalar','positive'});
validateattributes(Ts,   {'double'}, {'scalar','positive'});

%% Minimum-time continuous profile

tAccelToVmax = vMax / aMax;
dAccelToVmax = 0.5 * aMax * tAccelToVmax^2;

if D >= 2*dAccelToVmax

    % True trapezoidal profile: vMax is reached.
    tAccel = tAccelToVmax;
    tCruise = (D - 2*dAccelToVmax) / vMax;
    vPeak = vMax;
    profileType = 'trapezoidal';

else

    % Short move: triangular velocity profile.
    tAccel = sqrt(D / aMax);
    tCruise = 0;
    vPeak = aMax * tAccel;
    profileType = 'triangular';

end

Tmin = 2*tAccel + tCruise;

%% Align duration to the 30 ms sample grid

nIntervals = ceil(Tmin / Ts - 1e-12);
Tfinal = nIntervals * Ts;

timeScale = Tfinal / Tmin;

% Uniform time scaling:
%   velocity     -> v / k
%   acceleration -> a / k^2
tAccelScaled = tAccel * timeScale;
tCruiseScaled = tCruise * timeScale;

aUsed = aMax / timeScale^2;
vUsed = vPeak / timeScale;

% Phase edges
t1 = tAccelScaled;
t2 = t1 + tCruiseScaled;

% Distance covered during scaled acceleration
dAccel = 0.5 * aUsed * t1^2;

%% Sample every Ts

t = (0:nIntervals).' * Ts;

x = zeros(size(t));
v = zeros(size(t));
a = zeros(size(t));

for n = 1:numel(t)

    tn = t(n);

    if tn <= t1 + 1e-12

        % Acceleration phase
        x(n) = 0.5 * aUsed * tn^2;
        v(n) = aUsed * tn;
        a(n) = aUsed;

    elseif tn <= t2 + 1e-12

        % Constant-velocity phase
        tau = tn - t1;

        x(n) = dAccel + vUsed * tau;
        v(n) = vUsed;
        a(n) = 0;

    else

        % Deceleration phase
        tau = tn - t2;

        xAtDecelStart = dAccel + vUsed * tCruiseScaled;

        x(n) = xAtDecelStart + ...
               vUsed * tau - ...
               0.5 * aUsed * tau^2;

        v(n) = vUsed - aUsed * tau;
        a(n) = -aUsed;

    end

end

%% Force exact boundary conditions

x(1)   = 0;
x(end) = D;

v(1)   = 0;
v(end) = 0;

% Ideal trapezoidal velocity has instantaneous acceleration changes.
a(1)   = 0;
a(end) = 0;

%% Normalize position to 0...1

s = x / D;
s = min(max(s,0),1);

s(1)   = 0;
s(end) = 1;

%% Return information

info.profileType = profileType;
info.minimumTime = Tmin;
info.finalTime = Tfinal;
info.timeScale = timeScale;
info.tAccel = tAccelScaled;
info.tCruise = tCruiseScaled;
info.vPeak = vUsed;
info.aUsed = aUsed;

end
