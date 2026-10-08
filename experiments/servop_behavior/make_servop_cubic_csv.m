%% make_servop_cubic_csv.m
% Dedicated ServoP behavior experiment: SAME Cartesian segment as MoveL.
% Units: X/Y/Z in mm, Rx/Ry/Rz in deg, t in seconds.
% Uses a single normalized cubic (zero endpoint velocity), sampled at 30 ms.
% This script does NOT read any previous CSV.
clear; clc;

%% USER SETTINGS
Ts = 0.030;
poseStart = [-600, -400, 250, -90, 0, 90];
poseEnd   = [-600,  400, 250, -90, 0, 90];
vMax_mm_s = 600;
aMax_mm_s2 = 2000;
makePlot = true;
outputCsv = fullfile(fileparts(mfilename('fullpath')), 'points_servop_cubic.csv');

%% Generate path (only TCP translation determines speed constraints)
delta = poseEnd - poseStart;
translation = delta(1:3);
D = norm(translation);
if D <= 0 || ~all(isfinite([poseStart, poseEnd]))
    error('Specify finite, distinct Cartesian endpoints.');
end
if any(delta(4:6) ~= 0)
    error('This experiment requires constant tool orientation.');
end
if Ts <= 0 || vMax_mm_s <= 0 || aMax_mm_s2 <= 0
    error('Ts, vMax, and aMax must all be positive.');
end

% s(u) = 3*u^2 - 2*u^3,  u=t/T
% max(ds/dt) = 1.5/T, max(abs(d2s/dt2)) = 6/T^2
Tmin = max(1.5*D/vMax_mm_s, sqrt(6*D/aMax_mm_s2));
nIntervals = max(1, ceil(Tmin/Ts - 1e-12));
Tfinal = nIntervals*Ts;
t = (0:nIntervals).'*Ts;
u = t/Tfinal;
s = 3*u.^2 - 2*u.^3;
sd = (6*u - 6*u.^2)/Tfinal;
sdd = (6 - 12*u)/Tfinal^2;
sddd = (-12/Tfinal^3)*ones(size(u));

Q = bsxfun(@plus, poseStart, bsxfun(@times, s, delta));
Q(1,:) = poseStart;
Q(end,:) = poseEnd;
mode = repmat({'ServoP'}, numel(t), 1);
tab = table(mode, Q(:,1), Q(:,2), Q(:,3), Q(:,4), Q(:,5), Q(:,6), ...
    'VariableNames', {'mode','x1','x2','x3','x4','x5','x6'});
writetable(tab, outputCsv);

fprintf('CSV: %s\n', outputCsv);
fprintf('Cartesian distance: %.1f mm\n', D);
fprintf('Samples: %d | sample period: %.3f s | duration: %.3f s\n', ...
    numel(t), Ts, Tfinal);
fprintf('Cubic theoretical speed peak: %.3f mm/s\n', max(abs(D*sd)));
fprintf('Cubic theoretical accel peak: %.3f mm/s^2\n', max(abs(D*sdd)));
fprintf('Cubic theoretical jerk magnitude: %.3f mm/s^3\n', max(abs(D*sddd)));

if makePlot
    figure('Name', 'ServoP cubic reference — MoveL endpoints');
    subplot(4,1,1); plot(t, Q(:,2), 'LineWidth', 1.3);
    ylabel('Y [mm]'); grid on; title('Cubic ServoP reference');
    subplot(4,1,2); plot(t, D*sd, 'LineWidth', 1.3);
    ylabel('Speed [mm/s]'); grid on;
    subplot(4,1,3); plot(t, D*sdd, 'LineWidth', 1.3);
    ylabel('Accel [mm/s^2]'); grid on;
    subplot(4,1,4); plot(t, D*sddd, 'LineWidth', 1.3);
    ylabel('Jerk [mm/s^3]'); xlabel('Time [s]'); grid on;
end
