%% generate_piecewise_sweep.m
% MATLAB is the editable source of the nine-case parameter sweep.
%
% From repository root:
%   run('experiments/piecewise_sweep/generate_piecewise_sweep.m')
%
% Produces:
%   experiments/piecewise_sweep/case_matrix.csv
%   experiments/trapezoidal/points_trapezoidal_sweep_01.csv ... _09.csv
%   experiments/double_s/points_double_s_sweep_01.csv ... _09.csv
%
% No input CSV is required. Every exported trajectory is reopened, checked,
% reported in the Command Window, and plotted (if enabled).
%
% The Python runner reads case_matrix.csv at --list-cases time, verifies
% the generated CSV against independent analytical equations, and pins the
% file SHA-256 for the physical run. DO NOT use --execute before inspecting
% the regenerated paths, poses, limits and scope configuration.

clear; clc;

%% ====================== EDIT THESE SETTINGS ============================
Ts = 0.030;  % ServoP interval [s], must stay 30 ms for this experiment
startPose = [-600 -400 250 -90 0 90];
endPose   = [-600  400 250 -90 0 90];

% Each row = [V (mm/s), A (mm/s^2), J (mm/s^3)].
% Trapezoidal ignores J; Double-S and online Ruckig use all three limits.
% The L9 design has every V/A, V/J and A/J pair once.
caseMatrix = [
    300   500   6000;
    300   800  10000;
    300  1100  16000;
    380   500  10000;
    380   800  16000;
    380  1100   6000;
    460   500  16000;
    460   800   6000;
    460  1100  10000
];

makePlots = true;         % Position, velocity; Double-S also jerk
printEveryCsvRow = false; % true prints every saved CSV row to Command Window
%% ======================================================================

root = fileparts(mfilename('fullpath'));
experimentsDir = fileparts(root);
profiles = {'trapezoidal','double_s'};

assert(isnumeric(caseMatrix) && isequal(size(caseMatrix),[9,3]), ...
    'caseMatrix must have exactly 9 rows and 3 columns [V A J]');
assert(all(isfinite(caseMatrix(:))) && all(caseMatrix(:)>0), ...
    'All velocity, acceleration and jerk limits must be finite, positive');
for col = 1:3
    assert(numel(unique(caseMatrix(:,col)))==3, ...
        'The L9 design requires 3 distinct levels per parameter');
end
for pair = [1 2; 1 3; 2 3]'
    assert(size(unique(caseMatrix(:,pair),'rows'),1)==9, ...
        'L9 design requires each pair of parameter levels exactly once');
end
assert(isnumeric(startPose) && isnumeric(endPose) && ...
    numel(startPose)==6 && numel(endPose)==6 && ...
    all(isfinite(startPose)) && all(isfinite(endPose)), ...
    'Start and end poses must have six finite coordinates');
startPose = reshape(startPose,1,6);
endPose   = reshape(endPose,1,6);
delta = endPose-startPose;
assert(all(abs(delta(4:6))<1e-12), ...
    'Only Cartesian translation is supported (orientation is fixed)');
D = norm(delta(1:3));
assert(D>0, 'Cartesian start and end positions must differ');
assert(abs(Ts-.03)<1e-12, 'Study requires 30 ms command interval');

% Validate the WHOLE design before changing any output file.
for profileIndex = 1:numel(profiles)
    for c = 1:size(caseMatrix,1)
        V=caseMatrix(c,1); A=caseMatrix(c,2); J=caseMatrix(c,3);
        computeParameters(profiles{profileIndex},D,V,A,J,Ts);
    end
end

matrixPath = fullfile(root,'case_matrix.csv');
fid = fopen(matrixPath,'w');
assert(fid~=-1, 'Unable to open case matrix CSV for writing');
fprintf(fid,'case,velocity_mm_s,acceleration_mm_s2,jerk_mm_s3\n');
for c=1:9
    fprintf(fid,'%d,%.12g,%.12g,%.12g\n',c,caseMatrix(c,:));
end
fclose(fid);
savedMatrix=readtable(matrixPath);
assert(isequal(savedMatrix.Properties.VariableNames, ...
    {'case','velocity_mm_s','acceleration_mm_s2','jerk_mm_s3'}), ...
    'MATLAB case matrix header mismatch');
assert(height(savedMatrix)==9, 'MATLAB case matrix count mismatch');
assert(isequal(savedMatrix.case,(1:9)'), 'MATLAB case numbering mismatch');
assert(max(abs(savedMatrix{:,2:4}-caseMatrix),[],'all')<1e-9, ...
    'MATLAB case matrix values were not saved correctly');

fprintf('\nMATLAB PIECEWISE PARAMETER SWEEP\n');
fprintf('Pose start: [%s]\n',num2str(startPose,' %.6g'));
fprintf('Pose end:   [%s]\n',num2str(endPose,' %.6g'));
fprintf('Path length: %.3f mm | Sampling: %.3f s\n',D,Ts);
fprintf('Case matrix: %s\n',matrixPath);
fprintf('  #         V(mm/s)     A(mm/s2)     J(mm/s3)\n');
for c=1:9
    fprintf('%3d       %9.3f   %10.3f   %11.3f\n',c,caseMatrix(c,:));
end

for profileIndex=1:numel(profiles)
    profile=profiles{profileIndex};
    folder=fullfile(experimentsDir,profile);
    if makePlots
        posFig=figure('Name',[profile ' | 9 positions'], ...
                      'NumberTitle','off');
        velFig=figure('Name',[profile ' | 9 velocities'], ...
                      'NumberTitle','off');
        if strcmp(profile,'double_s')
            jerkFig=figure('Name','Double-S | 9 jerk profiles', ...
                           'NumberTitle','off');
        end
    end

    fprintf('\n--- %s ---\n',upper(profile));
    fprintf('Case | requested V/A/J | eff. peak V / A / J | duration | samples | verification\n');
    for c=1:9
        V=caseMatrix(c,1); A=caseMatrix(c,2); J=caseMatrix(c,3);
        p=computeParameters(profile,D,V,A,J,Ts);
        t=(0:p.nIntervals)'*Ts;
        x=zeros(size(t)); vel=x; accel=x; jerk=x;
        for k=1:numel(t)
            [x(k),vel(k),accel(k),jerk(k)] = ...
                profileState(profile,t(k),D,p);
        end
        x(1)=0; x(end)=D;
        vel(1)=0; vel(end)=0;
        Q=bsxfun(@plus,startPose,(x/D)*delta);
        Q(1,:)=startPose;
        Q(end,:)=endPose;

        outputPath=fullfile(folder,sprintf('points_%s_sweep_%02d.csv',profile,c));
        fid=fopen(outputPath,'w');
        assert(fid~=-1,['Unable to write ' outputPath]);
        fprintf(fid,'mode,x1,x2,x3,x4,x5,x6\n');
        for k=1:size(Q,1)
            fprintf(fid,'ServoP,%.12f,%.12f,%.12f,%.12f,%.12f,%.12f\n',Q(k,:));
        end
        fclose(fid);

        % Read back exactly what Python will consume, not in-memory Q alone.
        imported=readtable(outputPath);
        expectedHeader={'mode','x1','x2','x3','x4','x5','x6'};
        assert(isequal(imported.Properties.VariableNames,expectedHeader), ...
            'CSV header mismatch');
        assert(height(imported)==numel(t),'Wrong number of samples');
        assert(all(strcmp(cellstr(string(imported.mode)),'ServoP')), ...
            'CSV mode mismatch');
        saved=imported{:,2:7};
        assert(isequal(size(saved),size(Q)), 'CSV pose matrix size mismatch');
        assert(all(isfinite(saved(:))), 'Invalid numeric values in CSV');
        assert(max(abs(saved(:)-Q(:)))<2e-6, 'CSV read-back mismatch');
        assert(all(diff(saved(:,2))>=-1e-7), 'Y is not monotonic');
        assert(max(abs(saved(1,:)-startPose))<2e-6,'Wrong start pose');
        assert(max(abs(saved(end,:)-endPose))<2e-6,'Wrong end pose');

        if strcmp(profile,'trapezoidal')
            fprintf(' %02d  | V=%g A=%g        | %7.2f / %8.2f / --       | %6.2fs | %3d | PASS\n', ...
                c,V,A,p.peakV,p.peakA,p.duration,numel(t));
        else
            fprintf(' %02d  | V=%g A=%g J=%g | %7.2f / %8.2f / %9.1f | %6.2fs | %3d | PASS\n', ...
                c,V,A,J,p.peakV,p.peakA,p.peakJ,p.duration,numel(t));
        end
        fprintf('       CSV: %s\n',outputPath);
        fprintf('       First: [%s] | Last: [%s]\n', ...
                num2str(saved(1,:),' %.6f'),num2str(saved(end,:),' %.6f'));
        if printEveryCsvRow
            type(outputPath); % Explicit opt-in: prints all 18 CSV contents.
        end

        if makePlots
            figure(posFig);
            subplot(3,3,c);
            plot(t,saved(:,2),'LineWidth',1.2); grid on;
            title(sprintf('Case %d | V %g, A %g',c,V,A));
            xlabel('Time (s)'); ylabel('TCP Y (mm)');

            figure(velFig);
            subplot(3,3,c);
            plot(t,vel,'LineWidth',1.2); grid on;
            title(sprintf('Case %d | V %g, A %g',c,V,A));
            xlabel('Time (s)'); ylabel('Speed (mm/s)');

            if strcmp(profile,'double_s')
                figure(jerkFig);
                subplot(3,3,c);
                stairs(t,jerk,'LineWidth',1.2); grid on;
                title(sprintf('Case %d | J %g',c,J));
                xlabel('Time (s)'); ylabel('Jerk (mm/s^3)');
            end
        end
    end
end
fprintf('\nDONE: 18 MATLAB-generated, CSV-read-back-checked trajectories.\n');
fprintf('Python preflight: python main.py --experiment double_s --list-cases\n');

%% ============================ FUNCTIONS ===============================
function p=computeParameters(profile,D,V,A,J,Ts)
% Symmetric, rest-to-rest minimum-time profile with full V/A plateaus.
% The L9 case limits chosen above always satisfy these phase conditions.
if strcmp(profile,'trapezoidal')
    tj=0;
    ta=V/A;
    ramp=ta;
elseif strcmp(profile,'double_s')
    tj=A/J;
    ta=V/A-tj;
    assert(ta>0,'Double-S needs V/A > A/J to reach peak A');
    ramp=2*tj+ta;  % = V/A + A/J
else
    error('Unknown profile: %s',profile);
end
cruise=D/V-ramp;
assert(cruise>0,'Distance too short to reach V: choose lower V or higher A/J');
Tmin=D/V+ramp;
n=ceil(Tmin/Ts-1e-12);
T=n*Ts;
scale=T/Tmin;
p.duration=T;
p.nIntervals=n;
p.ramp=ramp*scale;
p.jerkRamp=tj*scale;
p.accelFlat=ta*scale;
p.peakV=V/scale;
p.peakA=A/scale^2;
p.peakJ=J/scale^3;
end

function [x,v,a,j]=profileState(profile,t,D,p)
T=p.duration;
r=p.ramp;
t=min(max(t,0),T);
if t<=r
    [x,v,a,j]=firstRamp(profile,t,p);
elseif t>=T-r
    [smallX,v,smallA,j]=firstRamp(profile,T-t,p);
    x=D-smallX;
    a=-smallA;
else
    x=p.peakV*r/2+p.peakV*(t-r);
    v=p.peakV; a=0; j=0;
end
end

function [x,v,a,j]=firstRamp(profile,t,p)
A=p.peakA;
if strcmp(profile,'trapezoidal')
    x=A*t^2/2;
    v=A*t;
    a=A;
    j=0; % Ideal jerk is impulsive at acceleration transitions.
    return;
end
tj=p.jerkRamp;
ta=p.accelFlat;
J=p.peakJ;
if t<=tj
    x=J*t^3/6;
    v=J*t^2/2;
    a=J*t;
    j=J;
elseif t<=tj+ta
    d=t-tj;
    x1=J*tj^3/6;
    v1=A*tj/2;
    x=x1+v1*d+A*d^2/2;
    v=v1+A*d;
    a=A;
    j=0;
else
    d=t-tj-ta;
    x1=J*tj^3/6;
    v1=A*tj/2;
    x2=x1+v1*ta+A*ta^2/2;
    v2=v1+A*ta;
    x=x2+v2*d+A*d^2/2-J*d^3/6;
    v=v2+A*d-J*d^2/2;
    a=A-J*d;
    j=-J;
end
end
