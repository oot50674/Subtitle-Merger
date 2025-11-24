$(document).ready(function() {
    // 초기 상태 설정
    $('#enable-basic-merge').trigger('change');
    $('#enable-duplicate-merge').trigger('change');
    $('#enable-end-start-merge').trigger('change');
    $('#enable-min-length-merge').trigger('change');
    $('#enable-ai-merge').trigger('change');
    $('#enable-min-duration-remove').trigger('change'); // 최소 자막 길이 제거 옵션 초기 상태 설정
    $('#enable-segment-analyzer').trigger('change');
    
    // 캐시에서 자막 병합 옵션 설정 값 복구
    var cachedOptions = localStorage.getItem('subtitleMergeOptions');
    var defaultAnalyzerLanguage = 'en';
    var supportedAnalyzerLanguages = ['en', 'ja', 'ko'];
    if (cachedOptions) {
        var options = JSON.parse(cachedOptions);
        
        // 체크박스 설정 복구
        $('#enable-basic-merge').prop('checked', options.enableBasicMerge);
        $('#enable-space-merge').prop('checked', options.enableSpaceMerge);
        $('#enable-duplicate-merge').prop('checked', options.enableDuplicateMerge);
        $('#enable-end-start-merge').prop('checked', options.enableEndStartMerge);
        $('#enable-min-length-merge').prop('checked', options.enableMinLengthMerge);
        $('#enable-ai-merge').prop('checked', options.enableAIMerge);
        $('#enable-min-duration-remove').prop('checked', options.enableMinDurationRemove);
        $('#enable-segment-analyzer').prop('checked', !!options.enableSegmentAnalyzer);
        
        // 숫자 입력 필드 설정 복구
        $('#min-text-length').val(options.minTextLength);
        $('#max-merge-count').val(options.maxMergeCount);
        $('#max-text-length').val(options.maxTextLength);
        $('#max-basic-gap').val(options.maxBasicGap);
        $('#max-duplicate-gap').val(options.maxDuplicateGap);
        $('#max-end-start-gap').val(options.maxEndStartGap);
        // similarityThreshold option removed
        $('#min-duration-ms').val(options.minDurationMs || 300);
        $('#candidate-chunk-size').val(options.candidateChunkSize || 3);
        var cachedLanguage = options.segmentAnalyzerLanguage;
        if (typeof cachedLanguage !== 'string') {
            cachedLanguage = defaultAnalyzerLanguage;
        } else {
            cachedLanguage = cachedLanguage.toLowerCase();
            if (supportedAnalyzerLanguages.indexOf(cachedLanguage) === -1) {
                cachedLanguage = defaultAnalyzerLanguage;
            }
        }
        $('#segment-analyzer-language').val(cachedLanguage);
    } else {
        $('#candidate-chunk-size').val(3);
        $('#segment-analyzer-language').val(defaultAnalyzerLanguage);
    }

    // 개별 체크박스 변경 시 관련 숫자 입력 필드 활성화/비활성화
    $('#enable-basic-merge').change(function() {
        $('#max-merge-count, #max-text-length, #max-basic-gap').prop('disabled', !$(this).is(':checked'));
    });
    
    $('#enable-min-length-merge').change(function() {
        $('#min-text-length').prop('disabled', !$(this).is(':checked'));
    });
    
    $('#enable-duplicate-merge').change(function() {
        $('#max-duplicate-gap').prop('disabled', !$(this).is(':checked'));
    });
    
    $('#enable-end-start-merge').change(function() {
        $('#max-end-start-gap').prop('disabled', !$(this).is(':checked'));
    });
    
    // similarity merge option removed
    
    $('#enable-min-duration-remove').change(function() { // 최소 자막 길이 제거 옵션 활성화/비활성화
        $('#min-duration-ms').prop('disabled', !$(this).is(':checked'));
    });

    $('#enable-segment-analyzer').change(function() {
        var disabled = !$(this).is(':checked');
        $('#segment-analyzer-language').prop('disabled', disabled);
        $('#candidate-chunk-size').prop('disabled', disabled);
    });
    
    // 초기 상태 설정 트리거
    $('#enable-basic-merge').trigger('change');
    $('#enable-min-length-merge').trigger('change');
    $('#enable-duplicate-merge').trigger('change');
    $('#enable-end-start-merge').trigger('change');
    // similarity merge option removed
    $('#enable-min-duration-remove').trigger('change'); // 최소 자막 길이 제거 옵션 초기 상태 트리거
    $('#enable-segment-analyzer').trigger('change');

    $('#process-btn').click(function() {
        var files = $('#srt-files')[0].files;
        // 자막 병합 옵션 설정
        var analyzerLanguage = $('#segment-analyzer-language').val();
        if (typeof analyzerLanguage !== 'string') {
            analyzerLanguage = defaultAnalyzerLanguage;
        } else {
            analyzerLanguage = analyzerLanguage.toLowerCase();
            if (supportedAnalyzerLanguages.indexOf(analyzerLanguage) === -1) {
                analyzerLanguage = defaultAnalyzerLanguage;
            }
        }
        var options = {
            enableBasicMerge: $('#enable-basic-merge').is(':checked'),      // 기본 병합 기능 활성화 여부
            enableSpaceMerge: $('#enable-space-merge').is(':checked'),      // 병합 시 띄어쓰기 추가 여부
            enableDuplicateMerge: $('#enable-duplicate-merge').is(':checked'), // 내용과 싱크가 동일한 자막 병합 활성화 여부
            enableEndStartMerge: $('#enable-end-start-merge').is(':checked'),  // 앞 자막의 뒷 부분과 다음 자막의 내용이 동일한 경우 병합 활성화 여부
            enableMinLengthMerge: $('#enable-min-length-merge').is(':checked'), // 병합 시 각 자막의 최소 문자 수 조건 활성화 여부
            enableAIMerge: $('#enable-ai-merge').is(':checked'),            // AI 기반 자막 병합 활성화 여부
            enableMinDurationRemove: $('#enable-min-duration-remove').is(':checked'),
            enableSegmentAnalyzer: $('#enable-segment-analyzer').is(':checked'),
            minTextLength: parseInt($('#min-text-length').val()) || 1,      // 병합 시 각 자막의 최소 문자 수
            maxMergeCount: parseInt($('#max-merge-count').val()) || 2,      // 병합할 최대 자막 개수
            candidateChunkSize: parseInt($('#candidate-chunk-size').val()) || 3, // 비교할 자막 청크 크기
            maxTextLength: parseInt($('#max-text-length').val()) || 50,     // 최대 병합 문자열 길이
            maxBasicGap: parseInt($('#max-basic-gap').val()) || 500,        // 기본 병합 시간 간격 (밀리초)
            maxDuplicateGap: parseInt($('#max-duplicate-gap').val()) || 300, // 중복 병합 시간 간격 (밀리초)
            maxEndStartGap: parseInt($('#max-end-start-gap').val()) || 300,   // 앞뒤 자막 병합 시간 간격 (밀리초)
            // similarityThreshold removed
            minDurationMs: parseInt($('#min-duration-ms').val()) || 300,
            segmentAnalyzerLanguage: analyzerLanguage.toLowerCase()
        };

        // 디버깅용 옵션 출력 - 화면에도 표시
        console.log("병합 옵션:", options);
        // 옵션 설정 캐시 저장
        localStorage.setItem('subtitleMergeOptions', JSON.stringify(options));

        // 다운로드 링크 영역 초기화
        $('#download-links').empty();
        $('#save-all-wrapper').remove();

        if (files.length > 0) {
            // FormData 객체 생성
            var formData = new FormData();
            
            // 파일들 추가
            for (var i = 0; i < files.length; i++) {
                formData.append('files[]', files[i]);
            }
            
            // 옵션 데이터 추가
            formData.append('options', JSON.stringify(options));

            // AJAX 요청 전송
            $.ajax({
                url: '/process_subtitles',
                type: 'POST',
                data: formData,
                processData: false,
                contentType: false,
                success: function(response) {
                    // 서버로부터 받은 처리된 파일들에 대한 다운로드 링크 생성
                    if (response.files) {
                        processedFiles = []; // 처리된 파일들 초기화
                        response.files.forEach(function(file) {
                            var link = $('<a>')
                                .attr('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(file.content))
                                .attr('download', 'merged_' + file.name)
                                .text('다운로드: merged_' + file.name);
                            
                            var countInfo = $('<div class="line-count">')
                                .text('병합 전: ' + file.beforeCount + ' 라인, 병합 후: ' + file.afterCount + ' 라인');
                            
                    $('#download-links')
                        .append($('<div class="download-entry">').append(link, countInfo));
                            
                            // 처리된 파일들을 배열에 저장
                        processedFiles.push({
                            name: 'merged_' + file.name,
                            content: file.content
                        });
                    });
                        if (processedFiles.length > 1) {
                            addSaveAllButton();
                        } else {
                            $('#save-all-wrapper').remove();
                        }
                    } else if (response.error) {
                        alert('오류: ' + response.error);
                    }
                },
                error: function(xhr, status, error) {
                    alert('파일 처리 중 오류가 발생했습니다: ' + error);
                }
            });
        } else {
            // textarea 입력 처리
            var input = $('#input-srt').val();
            if (input.trim() === '') {
                alert('SRT 파일을 업로드하거나 자막 내용을 입력해주세요.');
                return;
            }

            $('#output-srt').val('병합 중...');

            $.ajax({
                url: '/process_text',
                type: 'POST',
                data: {
                    text: input,
                    options: JSON.stringify(options)
                },
                success: function(response) {
                    if (response.output) {
                        $('#output-srt').val(response.output);
                        $('#textarea-line-count').text(
                            '병합 전: ' + response.beforeCount + ' 라인, 병합 후: ' + response.afterCount + ' 라인'
                        );
                    } else if (response.error) {
                        alert('오류: ' + response.error);
                        $('#output-srt').val('');
                    }
                },
                error: function(xhr, status, error) {
                    alert('텍스트 처리 중 오류가 발생했습니다: ' + error);
                    $('#output-srt').val('');
                }
            });
        }
    });

    $('#copy-btn').click(function() {
        $('#output-srt').select();
        document.execCommand('copy');
        alert('결과가 복사되었습니다.');
    });

    // 파일 드래그 앤 드롭 기능 추가
    var dropZone = document.getElementById('drop-zone');
    
    // 드래그 오버 이벤트
    dropZone.addEventListener('dragover', function(e) {
        e.preventDefault();
        e.stopPropagation();
        this.style.backgroundColor = '#e9e9e9';
    });
    
    // 드래그 리브 이벤트
    dropZone.addEventListener('dragleave', function(e) {
        e.preventDefault();
        e.stopPropagation();
        this.style.backgroundColor = '';
    });
    
    // 드롭 이벤트
    dropZone.addEventListener('drop', function(e) {
        e.preventDefault();
        e.stopPropagation();
        this.style.backgroundColor = '';
        
        var files = e.dataTransfer.files;
        $('#srt-files')[0].files = files;
        $('#srt-files').change();
    });
    
    // drop-zone 클릭 이벤트 추가
    dropZone.addEventListener('click', function() {
        $('#srt-files').click();
    });
    
    // 파일 선택 시 이벤트
    $('#srt-files').change(function() {
        var fileList = $('#file-list');
        fileList.empty();
        var files = this.files;
        var fileNames = [];
        for (var i = 0; i < files.length; i++) {
            fileNames.push(files[i].name);
        }
        var displayText = fileNames.join(', ');
        if (displayText.length > 100) {
            displayText = displayText.substring(0, 97) + '...';
        }
        fileList.text(displayText);
        fileList.attr('title', fileNames.join('\n'));
        $('#file-count').text(files.length + '개의 파일이 선택되었습니다.');
    });
});

var processedFiles = []; // 처리된 파일들을 저장할 배열

// 각 그룹의 이전 상태를 저장할 객체
var previousState = {
    group1: {},
     group2: {}
};

// 그룹의 상태를 저장하는 함수
function saveGroupState(groupSelector) {
    $(groupSelector + ' input[type="checkbox"], ' + groupSelector + ' input[type="number"]').each(function() {
        var $input = $(this);
        var id = $input.attr('id');
        var group = groupSelector === '.option-group1' ? 'group1' : 'group2';
        previousState[group][id] = $input.attr('type') === 'checkbox' ? $input.prop('checked') : $input.val();
    });
}

// 그룹의 상태를 복원하는 함수
function restoreGroupState(groupSelector) {
    var group = groupSelector === '.option-group1' ? 'group1' : 'group2';
    Object.keys(previousState[group]).forEach(function(id) {
        var $input = $('#' + id);
        if ($input.attr('type') === 'checkbox') {
            $input.prop('checked', previousState[group][id]);
        } else {
            $input.val(previousState[group][id]);
        }
        $input.prop('disabled', false); // disabled 속성 제거
    });
}

// 입력 그룹 전체를 토글하는 함수
function toggleInputGroup(groupSelector, enable) {
    // 입력 그룹의 모든 입력 요소를 활성화 또는 비활성화
    $(groupSelector + ' input').each(function() {
        var $input = $(this);
        if ($input.attr('type') === 'number') {
            $input.prop('disabled', !enable);
        }
    });
}

function addSaveAllButton() {
    if ($('#save-all-wrapper').length === 0) {
        var wrapper = $('<div id="save-all-wrapper" class="save-all-wrapper"></div>');
        var saveAllButton = $('<button id="save-all-btn">전체 저장 (ZIP)</button>');
        wrapper.append(saveAllButton);
        $('#download-links').prepend(wrapper);
        $('#save-all-btn').click(function() {
            var zip = new JSZip();
            processedFiles.forEach(function(file) {
                zip.file(file.name, file.content);
            });
            zip.generateAsync({ type: 'blob' }).then(function(content) {
                saveAs(content, 'merged_files.zip');
            });
        });
    }
}
