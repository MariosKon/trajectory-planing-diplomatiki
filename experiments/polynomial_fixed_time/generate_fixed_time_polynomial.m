function generate_fixed_time_polynomial(profile, outputDir, makePlot)
%GENERATE_FIXED_TIME_POLYNOMIAL Fixed-time Cartesian ServoP references.
% This function does not read a CSV. It writes three independent profiles
% with 30 ms intervals, the same path and nominal durations as MoveL.
%
% Calling scripts:
%   experiments/cubic/make_cubic_csv.m
%   experiments/quintic/make_quintic_csv.m
%
% Duration is prescribed, NOT calculated from velocity/acceleration limits.
% CAUTION: Equal durations do not imply equal peak speed or acceleration.
if nargin < 3
    makePlot = true;
end
if ~ismember(profile, {'cubic','quintic'})
    error('Profile must be cubic or quintic.');
end
if ~exist(outputDir, 'dir')
    error('Missing output directory: %s', outputDir);
end

Ts = 0.030;                            % DOBOT ServoP command period [s]
durations = [3.93, 2.79, 2.31];        % approximately MoveL 50/75/100 %%
qStart = [-600, -400, 250, -90, 0, 90];
qEnd   = [-600,  400, 250, -90, 0, 90];
delta = qEnd - qStart;
distance = norm(delta(1:3));           % Cartesian translation only [mm]
if distance <= 0 || any(delta(4:6) ~= 0)
    error('This fixed-time study requires a pure Cartesian translation.');
end

fprintf('\n===========================================================\n');
fprintf(' %s POLYNOMIAL | FIXED-TIME SERVOP CSV EXPORT\n', upper(profile));
fprintf('===========================================================\n');
fprintf('Cartesian path: X=%.0f, Y=%.0f to %.0f mm, Z=%.0f\n', ...
    qStart(1), qStart(2), qEnd(2), qStart(3));
fprintf('Path length: %.3f mm | Sample time: %.3f s\n', distance, Ts);
fprintf('Output directory: %s\n', outputDir);
fprintf('All three cases will be exported and read back for verification.\n');
summary = zeros(numel(durations), 5);

for k = 1:numel(durations)
    requestedT = durations(k);
    intervals = round(requestedT / Ts);
    Tfinal = intervals * Ts;
    if abs(Tfinal - requestedT) > 1e-9
        error('Case %d: duration must be an exact multiple of 30 ms.', k);
    end

    t = (0:intervals).' * Ts;
    tau = t / Tfinal;
    if strcmp(profile, 'cubic')
        s = 3*tau.^2 - 2*tau.^3;
        sd = (6*tau - 6*tau.^2) / Tfinal;
        sdd = (6 - 12*tau) / (Tfinal^2);
        sddd = -12 * ones(size(tau)) / (Tfinal^3);
        peakVCoeff = 1.5;
        peakACoeff = 6;
        peakJCoeff = 12;
    else
        s = 10*tau.^3 - 15*tau.^4 + 6*tau.^5;
        sd = (30*tau.^2 - 60*tau.^3 + 30*tau.^4) / Tfinal;
        sdd = (60*tau - 180*tau.^2 + 120*tau.^3) / (Tfinal^2);
        sddd = (60 - 360*tau + 360*tau.^2) / (Tfinal^3);
        peakVCoeff = 15/8;
        peakACoeff = 10*sqrt(3)/3;
        peakJCoeff = 60;
    end

    s(1) = 0;
    s(end) = 1;
    Q = bsxfun(@plus, qStart, bsxfun(@times, s, delta));
    Q(1,:) = qStart;
    Q(end,:) = qEnd;

    if any(~isfinite(Q(:))) || any(diff(Q(:,2)) < -1e-7)
        error('Case %d: invalid or non-monotonic trajectory.', k);
    end

    peakV = peakVCoeff * distance / Tfinal;
    peakA = peakACoeff * distance / (Tfinal^2);
    peakJ = peakJCoeff * distance / (Tfinal^3);

    durationTag = strrep(sprintf('%.2f', Tfinal), '.', 'p');
    filename = sprintf('points_%s_T%s.csv', profile, durationTag);
    path = fullfile(outputDir, filename);
    fid = fopen(path, 'w');
    if fid < 0
        error('Cannot open CSV output: %s', path);
    end
    closer = onCleanup(@() fclose(fid));
    fprintf(fid, 'mode,x1,x2,x3,x4,x5,x6\n');
    for row = 1:size(Q,1)
        fprintf(fid, 'ServoP,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f\n', Q(row,:));
    end
    clear closer

    %% Reopen the actual exported file and verify its contents
    % Do not print PASS based solely on the in-memory trajectory.
    exported = readtable(path);
    expectedNames = {'mode','x1','x2','x3','x4','x5','x6'};
    if ~isequal(exported.Properties.VariableNames, expectedNames)
        error('CSV verification FAILED: incorrect column names in %s', path);
    end
    if height(exported) ~= size(Q,1)
        error('CSV verification FAILED: incorrect number of rows in %s', path);
    end
    if any(~strcmp(string(exported.mode), 'ServoP'))
        error('CSV verification FAILED: unexpected mode in %s', path);
    end
    stored = exported{:,2:7};
    if ~isequal(size(stored), size(Q)) || any(~isfinite(stored(:)))
        error('CSV verification FAILED: invalid numeric waypoints in %s', path);
    end
    maxPositionError = max(abs(stored(:) - Q(:)));
    if maxPositionError > 2e-6
        error('CSV verification FAILED: pose mismatch in %s (%.3g)', ...
            path, maxPositionError);
    end
    if any(diff(stored(:,2)) < -1e-7) || ...
       any(abs(stored(1,:) - qStart) > 2e-6) || ...
       any(abs(stored(end,:) - qEnd) > 2e-6)
        error('CSV verification FAILED: endpoints or Y monotonicity in %s', path);
    end

    summary(k,:) = [Tfinal, size(Q,1), peakV, peakA, peakJ];

    fprintf('\n-----------------------------------------------------------\n');
    fprintf('Case %d/%d | %s | T = %.2f s\n', ...
        k, numel(durations), upper(profile), Tfinal);
    fprintf('CSV file: %s\n', path);
    fprintf('Samples: %d (intervals: %d, step: %.0f ms)\n', ...
        size(Q,1), intervals, Ts*1000);
    fprintf('First pose: [%.3f %.3f %.3f %.3f %.3f %.3f]\n', stored(1,:));
    fprintf('Last pose:  [%.3f %.3f %.3f %.3f %.3f %.3f]\n', stored(end,:));
    fprintf('Peak speed (analytic):        %.3f mm/s\n', peakV);
    fprintf('Peak acceleration (analytic): %.3f mm/s^2\n', peakA);
    fprintf('Peak jerk (interior):         %.3f mm/s^3\n', peakJ);
    fprintf('CSV read-back: PASS (%d rows, ServoP, exact poses, monotonic Y)\n', ...
        height(exported));
    fprintf('Max CSV position rounding error: %.3g mm\n', maxPositionError);
    if peakV > 470.5
        warning(['Peak velocity %.2f mm/s exceeds the measured fastest ' ...
                 'MoveL plateau (~470.5 mm/s). Physical safety review required.'], peakV);
    end

    if makePlot
        figure('Name', sprintf('%s T=%.2fs', profile, Tfinal));
        subplot(4,1,1);
        plot(t, Q(:,2), 'LineWidth', 1.4);
        hold on;
        plot(t, stored(:,2), '.', 'MarkerSize', 6);
        hold off;
        legend('Analytic Y', 'Read-back CSV', 'Location', 'best');
        grid on; ylabel('Y [mm]');
        title(sprintf('%s Cartesian trajectory, T=%.2f s', profile, Tfinal));
        subplot(4,1,2);
        plot(t, distance * sd); grid on; ylabel('V [mm/s]');
        subplot(4,1,3);
        plot(t, distance * sdd); grid on; ylabel('A [mm/s^2]');
        subplot(4,1,4);
        plot(t, distance * sddd); grid on; ylabel('J [mm/s^3]');
        xlabel('Time [s]');
    end
end

fprintf('\n===========================================================\n');
fprintf(' %s - FINAL SUMMARY (all CSV files verified)\n', upper(profile));
fprintf('===========================================================\n');
fprintf('Case | Duration [s] | Points | Peak V [mm/s] | Peak A [mm/s^2] | Peak J [mm/s^3]\n');
for k = 1:size(summary,1)
    fprintf(' %d   | %7.2f      | %4d   | %10.2f    | %11.2f     | %12.2f\n', ...
        k, summary(k,1), round(summary(k,2)), ...
        summary(k,3), summary(k,4), summary(k,5));
end
fprintf('All %d CSV files passed read-back verification.\n', size(summary,1));
if makePlot
    fprintf('%d figures opened: position, velocity, acceleration and jerk.\n', ...
        numel(durations));
end
fprintf('===========================================================\n\n');
end
