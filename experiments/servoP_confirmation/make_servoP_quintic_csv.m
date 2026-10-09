%% make_servoP_quintic_csv.m
% Duration-controlled quintic Cartesian ServoP reference.
% Generates the fixed CSV for all 15 confirmation runs.
% The requested duration T is aligned upward to fixed Ts increments.
% For T = 2.00 s and Ts = 0.030 s: actual duration = 2.01 s.
clear; clc;

%% USER SETTINGS (Cartesian coordinates: mm and degrees)
poseStart = [-600, -400, 250, -90, 0, 90];
poseEnd   = [-600,  400, 250, -90, 0, 90];
T = 2.0;                  % requested trajectory duration [s]
Ts = 0.030;               % fixed robot setpoint interval [s]
makePlot = true;

% Write beside THIS script, not in the MATLAB working directory.
scriptFile = mfilename('fullpath');
if isempty(scriptFile)
    error('Run the saved make_servoP_quintic_csv.m file as a script.');
end
outputCsv = fullfile(fileparts(scriptFile), 'points_servoP_quintic.csv');

%% VALIDATE AND ALIGN TO SERVO PERIOD
if numel(poseStart) ~= 6 || numel(poseEnd) ~= 6 || ...
        any(~isfinite([poseStart, poseEnd]))
    error('Start and end poses must contain six finite values.');
end
if ~isfinite(T) || ~isfinite(Ts) || T <= 0 || Ts <= 0
    error('T and Ts must be positive finite numbers.');
end
delta = poseEnd - poseStart;
D = norm(delta(1:3));
if D <= 0
    error('Start and target positions must differ.');
end
if any(delta(4:6) ~= 0)
    error('This confirmation reference requires a fixed tool orientation.');
end
nIntervals = max(2, ceil(T / Ts - 1e-12));
Tactual = nIntervals * Ts;
t = (0:nIntervals).' * Ts;
u = t / Tactual;

%% QUINTIC WITH ZERO ENDPOINT VELOCITY AND ACCELERATION
% s(u) = 10*u^3 - 15*u^4 + 6*u^5
s = 10*u.^3 - 15*u.^4 + 6*u.^5;
sd = (30*u.^2 - 60*u.^3 + 30*u.^4) / Tactual;
sdd = (60*u - 180*u.^2 + 120*u.^3) / Tactual^2;
sddd = (60 - 360*u + 360*u.^2) / Tactual^3;

Q = bsxfun(@plus, poseStart, bsxfun(@times, s, delta));
Q(1,:) = poseStart;
Q(end,:) = poseEnd;

%% SAVE, CLOSE AND VERIFY CSV
[fid, errMsg] = fopen(outputCsv, 'w');
if fid < 0
    error('Cannot write %s: %s', outputCsv, errMsg);
end
fileGuard = onCleanup(@() fclose(fid));
fprintf(fid, 'mode,x1,x2,x3,x4,x5,x6\n');
for k = 1:size(Q, 1)
    fprintf(fid, 'ServoP,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f\n', Q(k,:));
end
clear fileGuard;  % Close and flush before verifying.
info = dir(outputCsv);
if isempty(info) || info.bytes < 100
    error('CSV could not be verified on disk: %s', outputCsv);
end

fprintf('\nCSV VERIFIED ON DISK\n');
fprintf('File: %s\n', outputCsv);
fprintf('File size: %d bytes\n', info.bytes);
fprintf('Number of points: %d\n', numel(t));
fprintf('Sample period: %.3f s\n', Ts);
fprintf('Requested T: %.3f s | actual T: %.3f s\n', T, Tactual);
fprintf('Path distance: %.3f mm\n', D);
fprintf('Quintic continuous peak TCP speed: %.3f mm/s\n', 1.875*D/Tactual);
fprintf('Quintic continuous peak TCP acceleration: %.3f mm/s^2\n', ...
    (10*sqrt(3)/3)*D/Tactual^2);
fprintf('Quintic max absolute jerk on segment: %.3f mm/s^3\n', ...
    60*D/Tactual^3);

%% DIAGNOSTIC PLOTS; A PLOT ERROR CANNOT INVALIDATE THE CSV
if makePlot
    try
        figure('Name', 'ServoP confirmation - quintic reference', ...
            'NumberTitle', 'off');
        subplot(4,1,1);
        plot(t, Q(:,2), 'LineWidth', 1.2); grid on;
        title('ServoP confirmation - quintic Y-position');
        ylabel('Y [mm]');
        subplot(4,1,2);
        plot(t, D*sd, 'LineWidth', 1.2); grid on;
        ylabel('Speed [mm/s]');
        subplot(4,1,3);
        plot(t, D*sdd, 'LineWidth', 1.2); grid on;
        ylabel('Accel [mm/s^2]');
        subplot(4,1,4);
        plot(t, D*sddd, 'LineWidth', 1.2); grid on;
        ylabel('Jerk [mm/s^3]');
        xlabel('Time [s]');
        drawnow;
    catch plotError
        warning('CSV saved successfully; plotting failed: %s', ...
            plotError.message);
    end
end
