%% make_double_s_csv.m
% Standalone Double-S CSV generator
% ---------------------------------
% This script DOES NOT read any input CSV.
%
% You define:
%   - start pose
%   - end pose
%   - velocity / acceleration / jerk limits
%   - fixed sample time (30 ms)
%
% It generates:
%   mode,x1,x2,x3,x4,x5,x6
%
% Example:
%   Start: [-600 -400 250 -90 0 90]
%   End:   [-600  400 250 -90 0 90]
%
% The trajectory is sampled every 30 ms.

clear;
clc;

%% ================= USER SETTINGS =================

outputCsv = 'points_double_s.csv';

Ts = 0.030;   % [s] fixed time between consecutive points

% Start and end pose:
qStart = [-600, -400, 250, -90, 0, 90];
qEnd   = [-600,  400, 250, -90, 0, 90];

% Motion limits for the main moving coordinate:
vMax = 500;    % [units/s]
aMax = 1500;   % [units/s^2]
jMax = 16000;   % [units/s^3]

% Text written in the first CSV column:
mode = 'ServoP';

makePlot = true;

%% =================================================

delta = qEnd - qStart;

if all(abs(delta) < 1e-12)
    error("Start and end poses are identical.");
end

% Use the coordinate with the largest displacement as the path driver.
[distance, driverAxis] = max(abs(delta));

% Generate a scalar normalized Double-S trajectory from 0 to 1.
[t, s, vPath, aPath, jPath, info] = ...
    doubleSRestToRest(distance, vMax, aMax, jMax, Ts);

% Apply the same normalized progress to all six coordinates.
Q = qStart + s .* delta;

% Make sure the endpoints are numerically exact.
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

fprintf("\nCSV generated successfully.\n");
fprintf("File: %s\n", outputCsv);
fprintf("Number of points: %d\n", N);
fprintf("Sample time: %.3f s\n", Ts);
fprintf("Motion duration: %.3f s\n", t(end));
fprintf("Driver coordinate: x%d\n", driverAxis);
fprintf("Maximum displacement: %.3f\n", distance);

fprintf("\nPeak values after 30 ms alignment:\n");
fprintf("Velocity:     %.3f\n", max(abs(vPath)));
fprintf("Acceleration: %.3f\n", max(abs(aPath)));
fprintf("Jerk:         %.3f\n", max(abs(jPath)));

fprintf("\nContinuous minimum duration: %.6f s\n", info.minimumTime);
fprintf("Final grid-aligned duration: %.6f s\n", info.finalTime);

%% Plot for verification

if makePlot
    figure("Name","Double-S trajectory");

    subplot(4,1,1)
    plot(t, Q(:,driverAxis), "LineWidth", 1.3);
    grid on;
    ylabel(sprintf("x%d",driverAxis));
    title("Double-S trajectory");

    subplot(4,1,2)
    plot(t, vPath, "LineWidth", 1.3);
    grid on;
    ylabel("Velocity");

    subplot(4,1,3)
    plot(t, aPath, "LineWidth", 1.3);
    grid on;
    ylabel("Acceleration");

    subplot(4,1,4)
    stairs(t, jPath, "LineWidth", 1.3);
    grid on;
    ylabel("Jerk");
    xlabel("Time [s]");
end


%% ============================================================
function [t, s, v, a, j, info] = ...
    doubleSRestToRest(D, vMax, aMax, jMax, Ts)
% Symmetric jerk-limited Double-S trajectory.
%
% Seven possible phases:
%
%   +J | 0 | -J | 0 | -J | 0 | +J
%
% Start:
%   position = 0
%   velocity = 0
%   acceleration = 0
%
% End:
%   position = D
%   velocity = 0
%   acceleration = 0
%
% The continuous minimum-time trajectory is calculated first.
% Then its duration is rounded UP to an exact multiple of Ts.
% Uniform time scaling ensures that velocity, acceleration and jerk
% limits are not exceeded.

validateattributes(D,    {'double'}, {'scalar','positive'});
validateattributes(vMax, {'double'}, {'scalar','positive'});
validateattributes(aMax, {'double'}, {'scalar','positive'});
validateattributes(jMax, {'double'}, {'scalar','positive'});
validateattributes(Ts,   {'double'}, {'scalar','positive'});

%% Determine minimum-time phase durations

if vMax >= aMax^2 / jMax

    % Acceleration limit can potentially be reached.
    Tj = aMax / jMax;

    TaAtVmax = vMax / aMax - Tj;

    % Distance required to reach vMax and return to rest.
    DAtVmax = vMax * (2*Tj + TaAtVmax);

    if D >= DAtVmax

        % Full Double-S with constant velocity section.
        Ta = TaAtVmax;
        Tv = (D - DAtVmax) / vMax;

    else

        % No constant velocity section.
        DAtAmax = 2 * aMax^3 / jMax^2;

        if D >= DAtAmax

            % Acceleration limit reached,
            % but velocity limit not reached.
            y = (-Tj + sqrt(Tj^2 + 4*D/aMax)) / 2;

            Ta = y - Tj;
            Tv = 0;

        else

            % Move too short to reach acceleration limit.
            Tj = (D / (2*jMax))^(1/3);

            Ta = 0;
            Tv = 0;

        end
    end

else

    % Velocity limit is low enough that aMax is never reached.
    TjAtVmax = sqrt(vMax / jMax);

    DAtVmax = 2 * jMax * TjAtVmax^3;

    if D >= DAtVmax

        Tj = TjAtVmax;
        Ta = 0;

        Tv = (D - DAtVmax) / vMax;

    else

        Tj = (D / (2*jMax))^(1/3);
        Ta = 0;
        Tv = 0;

    end
end

%% Continuous minimum duration

Tmin = 4*Tj + 2*Ta + Tv;

%% Align duration to 30 ms sample grid

nIntervals = ceil(Tmin / Ts - 1e-12);

Tfinal = nIntervals * Ts;

timeScale = Tfinal / Tmin;

% Scale all phase times.
phaseDuration = ...
    [Tj, Ta, Tj, Tv, Tj, Ta, Tj] * timeScale;

% Jerk decreases under time scaling.
J = jMax / timeScale^3;

phaseJerk = [J, 0, -J, 0, -J, 0, J];

phaseEdge = [0, cumsum(phaseDuration)];

%% Compute state at beginning of every phase

x0 = zeros(1,7);
v0 = zeros(1,7);
a0 = zeros(1,7);

xNow = 0;
vNow = 0;
aNow = 0;

for p = 1:7

    x0(p) = xNow;
    v0(p) = vNow;
    a0(p) = aNow;

    h = phaseDuration(p);
    jp = phaseJerk(p);

    xNow = ...
        xNow + ...
        vNow*h + ...
        0.5*aNow*h^2 + ...
        (1/6)*jp*h^3;

    vNow = ...
        vNow + ...
        aNow*h + ...
        0.5*jp*h^2;

    aNow = ...
        aNow + ...
        jp*h;

end

%% Sample trajectory every Ts

t = (0:nIntervals).' * Ts;

x = zeros(size(t));
v = zeros(size(t));
a = zeros(size(t));
j = zeros(size(t));

for n = 1:numel(t)

    tn = t(n);

    p = find( ...
        tn <= phaseEdge(2:end) + 1e-12, ...
        1, ...
        "first");

    if isempty(p)
        p = 7;
    end

    tau = tn - phaseEdge(p);

    jp = phaseJerk(p);

    x(n) = ...
        x0(p) + ...
        v0(p)*tau + ...
        0.5*a0(p)*tau^2 + ...
        (1/6)*jp*tau^3;

    v(n) = ...
        v0(p) + ...
        a0(p)*tau + ...
        0.5*jp*tau^2;

    a(n) = ...
        a0(p) + ...
        jp*tau;

    j(n) = jp;

end

%% Force exact terminal conditions

x(1)   = 0;
x(end) = D;

v(1)   = 0;
v(end) = 0;

a(1)   = 0;
a(end) = 0;

j(end) = 0;

%% Normalize path from 0 to 1

s = x / D;

s = min(max(s,0),1);

s(1)   = 0;
s(end) = 1;

%% Return information

info.minimumTime = Tmin;
info.finalTime = Tfinal;
info.timeScale = timeScale;
info.Tj = Tj * timeScale;
info.Ta = Ta * timeScale;
info.Tv = Tv * timeScale;

end
