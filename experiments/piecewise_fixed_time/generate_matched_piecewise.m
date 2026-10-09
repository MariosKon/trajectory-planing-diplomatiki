%% Fixed-time piecewise CSV generation, 800 mm Cartesian Y motion.
% Run from repository root:
% run('experiments/piecewise_fixed_time/generate_matched_piecewise.m')
% Produces the reference CSVs used by experiments/piecewise_fixed_time.py.
clear; clc;
here = fileparts(mfilename('fullpath'));
Ts = 0.030;
durations = [3.93 2.79 2.31];
labels = {'3p93','2p79','2p31'};
speeds = [300 400 460];
startPose = [-600 -400 250 -90 0 90];
endPose = [-600 400 250 -90 0 90];
D = norm(endPose(1:3)-startPose(1:3));
profiles = {'trapezoidal','double_s'};
makePlot = true;

for p = 1:numel(profiles)
    profile = profiles{p};
    outputFolder = fullfile(here,'..',profile);
    for c = 1:numel(durations)
        T = durations(c); V = speeds(c);
        intervals = round(T/Ts);
        assert(abs(intervals*Ts-T)<1e-9);
        r = T - D/V;
        assert(r > 0 && T-2*r > 0, 'No cruise phase');
        tj = r/4;
        A = V/(r-tj);
        J = A/tj;
        t = (0:intervals)'*Ts;
        x = zeros(size(t));
        for k=1:numel(t)
            tk = min(t(k),T);
            if tk <= r
                x(k) = rampDistance(profile,tk,r,tj,V,A,J);
            elseif tk >= T-r
                x(k) = D-rampDistance(profile,T-tk,r,tj,V,A,J);
            else
                x(k) = 0.5*V*r+V*(tk-r);
            end
        end
        Q = startPose+(x/D)*(endPose-startPose);
        Q(1,:) = startPose; Q(end,:) = endPose;
        mode = repmat({'ServoP'},numel(t),1);
        exported = table(mode,Q(:,1),Q(:,2),Q(:,3),Q(:,4),Q(:,5),Q(:,6), ...
            'VariableNames',{'mode','x1','x2','x3','x4','x5','x6'});
        path = fullfile(outputFolder, ['points_' profile '_T' labels{c} '.csv']);
        writetable(exported,path);
        check = readtable(path);
        restored = check{:,2:7};
        assert(height(check)==numel(t),'Incorrect sample count');
        assert(all(strcmp(check.mode,'ServoP')),'Unexpected mode');
        assert(max(abs(restored-Q),[],'all')<2e-6,'CSV readback mismatch');
        assert(all(diff(restored(:,2)) >= -1e-7),'Nonmonotonic Y');
        assert(max(abs(restored(1,:)-startPose)) < 1e-9);
        assert(max(abs(restored(end,:)-endPose)) < 1e-9);
        fprintf('%s T=%.2f s N=%d V=%.3f: CSV read-back PASS: %s\n',...
            profile,T,height(check),V,path);
        if makePlot
            figure('Name',[profile ' T=' num2str(T)]);
            subplot(2,1,1);
            plot(t,restored(:,2),'LineWidth',1.3); grid on;
            ylabel('Y (mm)'); title([profile ', T=' num2str(T) ' s']);
            subplot(2,1,2);
            plot(t(1:end-1),diff(restored(:,2))/Ts,'LineWidth',1.3);
            grid on; ylabel('Sample speed (mm/s)'); xlabel('Time (s)');
        end
    end
end

function x = rampDistance(profile,t,r,tj,V,A,J)
if strcmp(profile,'trapezoidal')
    x = 0.5*(V/r)*t^2;
    return
end
if t <= tj
    x = J*t^3/6;
elseif t <= r-tj
    d = t-tj;
    x = J*tj^3/6+(A*tj/2)*d+A*d^2/2;
else
    dFlat = r-2*tj;
    x1 = J*tj^3/6;
    v1 = A*tj/2;
    x2 = x1+v1*dFlat+A*dFlat^2/2;
    v2 = v1+A*dFlat;
    d = t-(r-tj);
    x = x2+v2*d+A*d^2/2-J*d^3/6;
end
end
