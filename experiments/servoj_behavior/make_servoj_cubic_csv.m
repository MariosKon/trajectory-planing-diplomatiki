%% make_servoj_cubic_csv.m
% Cubic joint-space reference for the ServoJ tracking-parameter experiment.
% No existing CSV is needed: hardcode all six start and end joint angles.
% Joint angles [degrees], angular velocity [deg/s], acceleration [deg/s^2].
clear; clc;

%% USER SETTINGS
Ts = 0.030;
qStart = [26, 53.8, 55.2, 71, 116, -180.2];
qEnd   = [-50, 54, 54.9, 71.4, 40, -180.2];
vMax_deg_s = 40;
aMax_deg_s2 = 60;
makePlot = true;
outputCsv = fullfile(fileparts(mfilename('fullpath')), 'points_servoj_cubic.csv');

%% Normalized cubic: s(u) = 3*u^2 - 2*u^3, u=t/T.
% Zero velocity at the beginning and end of the reference.
% Limits are applied jointwise, using the largest angular displacement.
if numel(qStart) ~= 6 || numel(qEnd) ~= 6 || ~all(isfinite([qStart, qEnd]))
    error('Both joint endpoints must contain six finite angles.');
end
if Ts <= 0 || vMax_deg_s <= 0 || aMax_deg_s2 <= 0
    error('Sampling interval, max speed and max acceleration must be positive.');
end

delta = qEnd - qStart;
D = max(abs(delta));
if D <= 0
    error('Start and end joint configurations must differ.');
end

tFromV = 1.5*D/vMax_deg_s;
tFromA = sqrt(6*D/aMax_deg_s2);
Tmin = max(tFromV, tFromA);
nIntervals = max(1, ceil(Tmin/Ts - 1e-12));
Tfinal = nIntervals*Ts;
t = (0:nIntervals).'*Ts;
u = t/Tfinal;

s = 3*u.^2 - 2*u.^3;
sd = (6*u - 6*u.^2)/Tfinal;
sdd = (6 - 12*u)/Tfinal^2;
sddd = (-12/Tfinal^3)*ones(size(t));
Q = bsxfun(@plus, qStart, bsxfun(@times, s, delta));
Q(1,:) = qStart;
Q(end,:) = qEnd;

mode = repmat({'ServoJ'}, numel(t), 1);
out = table(mode, Q(:,1), Q(:,2), Q(:,3), Q(:,4), Q(:,5), Q(:,6), ...
    'VariableNames', {'mode','j1','j2','j3','j4','j5','j6'});
writetable(out, outputCsv);

fprintf('ServoJ cubic CSV: %s\n', outputCsv);
fprintf('Joint displacements [deg]: %s\n', mat2str(delta));
fprintf('Samples: %d | Ts: %.3f s | duration: %.3f s\n', numel(t), Ts, Tfinal);
fprintf('Peak angular speed: %.3f deg/s\n', max(abs(sd))*D);
fprintf('Peak angular acceleration: %.3f deg/s^2\n', max(abs(sdd))*D);
fprintf('Reference jerk magnitude: %.3f deg/s^3\n', max(abs(sddd))*D);

if makePlot
    figure('Name', 'ServoJ cubic joint-space reference');
    subplot(4,1,1); plot(t, Q, 'LineWidth', 1.1); grid on;
    ylabel('Joint [deg]'); legend('J1','J2','J3','J4','J5','J6', 'Location','eastoutside');
    title('ServoJ — all six joints');
    subplot(4,1,2); plot(t, sd*delta, 'LineWidth', 1.1); grid on;
    ylabel('Speed [deg/s]');
    subplot(4,1,3); plot(t, sdd*delta, 'LineWidth', 1.1); grid on;
    ylabel('Accel [deg/s^2]');
    subplot(4,1,4); plot(t, sddd*delta, 'LineWidth', 1.1); grid on;
    ylabel('Jerk [deg/s^3]'); xlabel('Time [s]');
end
