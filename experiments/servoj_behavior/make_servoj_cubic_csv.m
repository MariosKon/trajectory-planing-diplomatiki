%% make_servoj_cubic_csv.m
% Standalone cubic trajectory generator for the six DOBOT joints.
% Generates CSV first, verifies it on disk, then draws diagnostic plots.
% Does not call or require legendcolorbarlayout.
clear;
clc;

%% CONFIGURATION (joint positions in degrees)
qStart = [26, 53.8, 55.2, 71, 116, -180.2];
qEnd   = [-50, 54, 54.9, 71.4, 40, -180.2];
Ts = 0.030;               % 30 ms
T = 2.0;                 % requested duration [s]
makePlot = true;

% Always save beside THIS script rather than in MATLAB's working directory.
scriptFile = mfilename('fullpath');
if isempty(scriptFile)
    error(['Run the saved script using make_servoj_cubic_csv, ' ...
           'not by evaluating a selection of lines.']);
end
scriptDir = fileparts(scriptFile);
outputCsv = fullfile(scriptDir, 'points_servoj_cubic.csv');

%% NORMALIZED CUBIC PROFILE
if numel(qStart) ~= 6 || numel(qEnd) ~= 6 || any(~isfinite([qStart qEnd]))
    error('Six finite joint angles are required for start and end.');
end
if ~isfinite(T) || Ts <= 0 || T <= 0
    error('T and Ts must be positive.');
end

delta = qEnd - qStart;
D = max(abs(delta));
if D <= 0
    error('The start and end joint positions must differ.');
end

nIntervals = max(2, ceil(T/Ts - 1e-12));
Tfinal = nIntervals*Ts;

t = (0:nIntervals)'*Ts;
u = t/Tfinal;
s = 3*u.^2 - 2*u.^3;
sd = (6*u - 6*u.^2)/Tfinal;
sdd = (6 - 12*u)/Tfinal^2;
sddd = (-12/Tfinal^3)*ones(size(t));

Q = bsxfun(@plus, qStart, bsxfun(@times, s, delta));
Q(1,:) = qStart;
Q(end,:) = qEnd;

%% WRITE CSV, CLOSE FILE, AND VERIFY ON DISK
% Basic text-file output avoids dependencies on table/writetable.
[fid, errMsg] = fopen(outputCsv, 'w');
if fid < 0
    error('Cannot create CSV at %s: %s', outputCsv, errMsg);
end
fileGuard = onCleanup(@() fclose(fid));
fprintf(fid, 'mode,j1,j2,j3,j4,j5,j6\n');
for k = 1:size(Q,1)
    fprintf(fid, 'ServoJ,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f\n', Q(k,:));
end
clear fileGuard;  % flush and close the CSV before verification

fileInfo = dir(outputCsv);
if isempty(fileInfo) || fileInfo.bytes < 100
    error('CSV was not saved correctly: %s', outputCsv);
end

fprintf('\nCSV VERIFIED ON DISK\n');
fprintf('Exact file: %s\n', outputCsv);
fprintf('File size: %d bytes\n', fileInfo.bytes);
fprintf('Joint displacements [deg]: %s\n', mat2str(delta));
fprintf('Samples: %d | Ts: %.3f s | requested T: %.3f s | actual T: %.3f s\n', numel(t), Ts, T, Tfinal);
fprintf('Peak angular speed: %.3f deg/s\n', max(abs(sd))*D);
fprintf('Peak angular acceleration: %.3f deg/s^2\n', max(abs(sdd))*D);
fprintf('Reference jerk magnitude: %.3f deg/s^3\n', max(abs(sddd))*D);

%% PLOTS ARE OPTIONAL; A GRAPHICS FAILURE CANNOT INVALIDATE THE CSV
if makePlot
    try
        f = figure('Name', 'ServoJ cubic joint-space trajectory', ...
                   'NumberTitle', 'off', 'Visible', 'on');

        subplot(4,1,1);
        plot(t, Q, 'LineWidth', 1.1);
        grid on;
        ylabel('Position [deg]');
        title('ServoJ - cubic joint-space trajectory');

        subplot(4,1,2);
        plot(t, sd*delta, 'LineWidth', 1.1);
        grid on;
        ylabel('Velocity [deg/s]');

        subplot(4,1,3);
        plot(t, sdd*delta, 'LineWidth', 1.1);
        grid on;
        ylabel('Acceleration [deg/s^2]');

        subplot(4,1,4);
        plot(t, sddd*delta, 'LineWidth', 1.1);
        grid on;
        ylabel('Jerk [deg/s^3]');
        xlabel('Time [s]');

        drawnow;
        fprintf('Figure generated (figure %d).\n', f.Number);
    catch plotError
        warning('CSV saved successfully, but graphics failed: %s', ...
                plotError.message);
    end
end
