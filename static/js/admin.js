        // 当前页面
        let currentPage = 'categories';
        
        // 单词分页
        let wordPage = 1;
        let wordPageSize = 20;
        let wordKeyword = '';
        let wordCategory = '';
        let totalWords = 0;
        let totalPages = 0;
        
        // 编辑状态
        let editingCategory = null;
        let editingWordId = null;
        
        // 删除回调
        let deleteCallback = null;

        // 切换侧边栏显示
        function toggleSidebar() {
            const sidebar = document.querySelector('.sidebar');
            const overlay = document.getElementById('sidebarOverlay');
            if (sidebar && overlay) {
                sidebar.classList.toggle('show');
                overlay.classList.toggle('show');
            }
        }
        
        // 切换页面
        function switchPage(page) {
            currentPage = page;
            
            // 更新菜单
            document.querySelectorAll('.menu-item').forEach(item => {
                item.classList.remove('active');
            });
            event.currentTarget.classList.add('active');
            
            // 更新标题
            const titles = {
                'categories': '分类管理',
                'words': '单词管理',
                'import': '批量导入',
                'logs': '日志管理',
                'settings': '设置',
                'ai': 'AI助手'
            };
            document.getElementById('pageTitle').textContent = titles[page];
            
            // 切换页面内容
            document.querySelectorAll('.page').forEach(p => {
                p.classList.remove('active');
            });
            document.getElementById('page-' + page).classList.add('active');
            
            // 非设置页面隐藏子导航
            if (page !== 'settings') {
                document.getElementById('settingsSubnav').style.display = 'none';
            }
            
            // 非批量导入导出页面隐藏子导航
            if (page !== 'import') {
                document.getElementById('importSubnav').style.display = 'none';
            }
            
            // 加载数据
            if (page === 'categories') {
                loadCategories();
            } else if (page === 'words') {
                loadWords();
                loadCategoryOptions();
            } else if (page === 'import') {
                // 显示批量导入导出页面子导航
                document.getElementById('importSubnav').style.display = 'flex';
                // 默认显示批量导出标签
                switchImportTab('export');
            } else if (page === 'logs') {
                loadLogActions();
                loadLogs();
            } else if (page === 'settings') {
                // 显示设置页面子导航
                document.getElementById('settingsSubnav').style.display = 'flex';
                // 默认显示站点信息标签
                switchSettingTab('site');
            } else if (page === 'ai') {
                // 加载聊天历史
                loadAIChatHistory();
            }
        }

        // 显示提示
        function showToast(message, type = 'success') {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = 'toast ' + type + ' show';
            setTimeout(() => {
                toast.classList.remove('show');
            }, 3000);
        }

        // ==================== 分类管理 ====================

        // 加载分类列表
        function loadCategories() {
            const tbody = document.getElementById('categoryTableBody');
            tbody.innerHTML = '<tr><td colspan="4" class="loading">加载中...</td></tr>';
            
            fetch('/api/admin/categories')
                .then(res => res.json())
                .then(categories => {
                    const searchKeyword = document.getElementById('categorySearch').value.toLowerCase();
                    const filtered = categories.filter(c => c.name.toLowerCase().includes(searchKeyword));
                    
                    if (filtered.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="4" class="empty">暂无分类</td></tr>';
                        return;
                    }
                    
                    let html = '';
                    filtered.forEach(cat => {
                        html += `
                        <tr>
                            <td><input type="checkbox" class="category-checkbox" value="${cat.id}" onchange="updateMergeButton()"></td>
                            <td>${cat.name}</td>
                            <td>${cat.count} 个</td>
                            <td>
                                <div class="action-buttons">
                                    <button class="btn btn-sm btn-secondary" onclick="editCategory(${cat.id}, '${cat.name}')">编辑</button>
                                    <button class="btn btn-sm btn-danger" onclick="deleteCategory(${cat.id}, '${cat.name}', ${cat.count})">删除</button>
                                </div>
                            </td>
                        </tr>
                        `;
                    });
                    tbody.innerHTML = html;
                    
                    // 更新统计
                    document.getElementById('categoryCount').textContent = categories.length;
                })
                .catch(err => {
                    tbody.innerHTML = '<tr><td colspan="4" class="empty">加载失败</td></tr>';
                    showToast('加载分类失败', 'error');
                });
        }

        // 分类搜索
        document.getElementById('categorySearch').addEventListener('input', function() {
            loadCategories();
        });

        // 显示添加分类弹窗
        function showAddCategoryModal() {
            editingCategory = null;
            document.getElementById('categoryModalTitle').textContent = '添加分类';
            document.getElementById('categoryNameInput').value = '';
            document.getElementById('categoryModal').classList.add('active');
        }

        // 编辑分类
        function editCategory(id, name) {
            editingCategory = { id: id, name: name };
            document.getElementById('categoryModalTitle').textContent = '编辑分类';
            document.getElementById('categoryNameInput').value = name;
            document.getElementById('categoryModal').classList.add('active');
        }

        // 关闭分类弹窗
        function closeCategoryModal() {
            document.getElementById('categoryModal').classList.remove('active');
            editingCategory = null;
        }

        // 保存分类
        function saveCategory() {
            const name = document.getElementById('categoryNameInput').value.trim();
            
            if (!name) {
                showToast('请输入分类名称', 'error');
                return;
            }
            
            let url, method, data;
            
            if (editingCategory) {
                // 编辑
                url = '/api/admin/category';
                method = 'PUT';
                data = { id: editingCategory.id, name: name };
            } else {
                // 添加
                url = '/api/admin/category';
                method = 'POST';
                data = { name: name };
            }
            
            fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
            .then(res => res.json())
            .then(result => {
                if (result.error) {
                    showToast(result.error, 'error');
                    return;
                }
                showToast(editingCategory ? '分类已更新' : '分类已添加');
                closeCategoryModal();
                loadCategories();
                loadCategoryOptions(); // 更新单词管理的分类选项
            })
            .catch(err => {
                showToast('操作失败', 'error');
            });
        }

        // 删除分类
        function deleteCategory(id, name, count) {
            deleteCallback = () => {
                fetch('/api/admin/category', {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: id })
                })
                .then(res => res.json())
                .then(result => {
                    if (result.error) {
                        showToast(result.error, 'error');
                        return;
                    }
                    showToast(`已删除分类及 ${result.deleted_count} 个单词`);
                    loadCategories();
                    loadCategoryOptions();
                    updateStats();
                })
                .catch(err => {
                    showToast('删除失败', 'error');
                });
            };
            
            document.getElementById('confirmMessage').innerHTML = 
                `确定要删除分类 "<strong>${name}</strong>" 吗？`;
            document.getElementById('confirmWarning').style.display = 'block';
            document.getElementById('confirmWarning').textContent = 
                `⚠️ 该分类下有 ${count} 个单词，删除后将一起删除，此操作不可撤销！`;
            document.getElementById('confirmModal').classList.add('active');
        }


        // 全选/取消全选分类
        function toggleSelectAllCategories(checkbox) {
            const checkboxes = document.querySelectorAll('.category-checkbox');
            checkboxes.forEach(cb => cb.checked = checkbox.checked);
            updateMergeButton();
        }

        // 更新合并按钮状态
        function updateMergeButton() {
            const checked = document.querySelectorAll('.category-checkbox:checked');
            const btn = document.getElementById('mergeCategoryBtn');
            if (btn) {
                btn.style.display = checked.length >= 2 ? 'inline-flex' : 'none';
            }
        }

        // 显示合并分类弹窗
        // 切换目标分类类型
        function switchMergeTargetType(type) {
            // 更新按钮样式和active类
            document.querySelectorAll('.tab-option').forEach(btn => {
                if (btn.dataset.type === type) {
                    btn.classList.add('active');
                    btn.style.background = '#2E75B6';
                    btn.style.color = 'white';
                } else {
                    btn.classList.remove('active');
                    btn.style.background = '#f5f7fa';
                    btn.style.color = '#666';
                }
            });

            // 显示对应的输入框
            if (type === 'existing') {
                document.getElementById('mergeTargetExistingGroup').style.display = 'block';
                document.getElementById('mergeTargetNewGroup').style.display = 'none';
            } else {
                document.getElementById('mergeTargetExistingGroup').style.display = 'none';
                document.getElementById('mergeTargetNewGroup').style.display = 'block';
            }
        }

        function showMergeCategoryModal() {
            const checked = document.querySelectorAll('.category-checkbox:checked');
            if (checked.length < 2) {
                showToast('请至少选择2个分类进行合并', 'error');
                return;
            }

            // 显示已选择的分类
            const list = document.getElementById('selectedCategoriesList');
            let names = [];
            checked.forEach(cb => {
                const row = cb.closest('tr');
                const name = row.querySelector('td:nth-child(2)').textContent;
                names.push(name);
            });
            list.innerHTML = names.map(n => `<div style="padding: 2px 0;">• ${n}</div>`).join('');

            // 重置表单
            switchMergeTargetType('existing');
            document.getElementById('mergeTargetCategory').value = '';
            document.getElementById('mergeNewCategoryName').value = '';

            // 加载目标分类选项
            const select = document.getElementById('mergeTargetCategory');
            select.innerHTML = '<option value="">请选择目标分类</option>';
            
            fetch('/api/admin/categories')
                .then(res => res.json())
                .then(categories => {
                    const checkedIds = Array.from(checked).map(cb => cb.value);
                    categories.forEach(cat => {
                        if (!checkedIds.includes(String(cat.id))) {
                            select.innerHTML += `<option value="${cat.id}">${cat.name}</option>`;
                        }
                    });
                });

            document.getElementById('mergeCategoryModal').classList.add('active');
        }

        // 关闭合并分类弹窗
        function closeMergeCategoryModal() {
            document.getElementById('mergeCategoryModal').classList.remove('active');
        }

        // 确认合并分类
        function confirmMergeCategories() {
            const checked = document.querySelectorAll('.category-checkbox:checked');
            const type = document.querySelector('.tab-option.active')?.dataset.type || 'existing';
            
            const fromIds = Array.from(checked).map(cb => parseInt(cb.value));
            const body = { from_ids: fromIds };

            if (type === 'existing') {
                const targetId = document.getElementById('mergeTargetCategory').value;
                if (!targetId) {
                    showToast('请选择目标分类', 'error');
                    return;
                }
                body.to_id = parseInt(targetId);
            } else {
                const targetName = document.getElementById('mergeNewCategoryName').value.trim();
                if (!targetName) {
                    showToast('请输入新分类名称', 'error');
                    return;
                }
                body.to_name = targetName;
            }

            fetch('/api/admin/categories/merge', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            })
            .then(res => res.json())
            .then(result => {
                if (result.success) {
                    showToast(result.message);
                    closeMergeCategoryModal();
                    loadCategories();
                    loadCategoryOptions();
                    updateStats();
                    // 取消全选
                    const selectAll = document.getElementById('selectAllCategories');
                    if (selectAll) selectAll.checked = false;
                } else {
                    showToast(result.message || '合并失败', 'error');
                }
            })
            .catch(err => {
                showToast('合并失败', 'error');
            });
        }

        // ==================== 单词管理 ====================

        // 加载分类选项
        function loadCategoryOptions() {
            fetch('/api/admin/categories')
                .then(res => res.json())
                .then(categories => {
                    const select = document.getElementById('wordCategoryFilter');
                    const modalSelect = document.getElementById('wordCategoryInput');
                    
                    // 保留第一个选项
                    select.innerHTML = '<option value="">全部分类</option>';
                    categories.forEach(cat => {
                        select.innerHTML += `<option value="${cat.name}">${cat.name}</option>`;
                    });
                    
                    // 弹窗里的分类选择
                    modalSelect.innerHTML = '<option value="">请选择分类</option>';
                    categories.forEach(cat => {
                        modalSelect.innerHTML += `<option value="${cat.name}">${cat.name}</option>`;
                    });
                    
                    // 设置当前筛选值
                    if (wordCategory) {
                        select.value = wordCategory;
                    }
                });
        }

        // 加载单词列表
        function loadWords() {
            const tbody = document.getElementById('wordTableBody');
            tbody.innerHTML = '<tr><td colspan="7" class="loading">加载中...</td></tr>';
            
            let url = `/api/admin/words?page=${wordPage}&page_size=${wordPageSize}`;
            if (wordKeyword) url += `&keyword=${encodeURIComponent(wordKeyword)}`;
            if (wordCategory) url += `&category=${encodeURIComponent(wordCategory)}`;
            
            fetch(url)
                .then(res => res.json())
                .then(result => {
                    const words = result.words;
                    totalWords = result.total;
                    totalPages = result.total_pages;
                    
                    if (words.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="7" class="empty">暂无单词</td></tr>';
                    } else {
                        let html = '';
                        words.forEach(word => {
                            html += `
                            <tr>
                                <td><input type="checkbox" class="word-checkbox" value="${word.id}" onchange="updateBatchButton()"></td>
                                <td><strong>${word.english_word}</strong></td>
                                <td><span class="category-tag">${word.category_name}</span></td>
                                <td class="phonetic">${word.british_phonetic || '-'}</td>
                                <td class="phonetic">${word.american_phonetic || '-'}</td>
                                <td style="max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${word.chinese_definition}">${word.chinese_definition}</td>
                                <td>
                                    <div class="action-buttons">
                                        <button class="btn btn-sm btn-secondary" onclick="editWord(${word.id})">编辑</button>
                                        <button class="btn btn-sm btn-danger" onclick="deleteWord(${word.id}, '${word.english_word}')">删除</button>
                                    </div>
                                </td>
                            </tr>
                            `;
                        });
                        tbody.innerHTML = html;
                    }
                    
                    // 更新分页
                    renderPagination();
                    
                    // 更新统计
                    document.getElementById('totalCount').textContent = totalWords;
                })
                .catch(err => {
                    tbody.innerHTML = '<tr><td colspan="7" class="empty">加载失败</td></tr>';
                    showToast('加载单词失败', 'error');
                });
        }

        // 渲染分页
        function renderPagination() {
            const pagination = document.getElementById('wordPagination');
            
            if (totalPages <= 1) {
                pagination.innerHTML = '';
                return;
            }
            
            let html = '';
            html += `<button onclick="goToPage(${wordPage - 1})" ${wordPage === 1 ? 'disabled' : ''}>上一页</button>`;
            html += `<span class="page-info">第 ${wordPage} / ${totalPages} 页，共 ${totalWords} 条</span>`;
            html += `<button onclick="goToPage(${wordPage + 1})" ${wordPage === totalPages ? 'disabled' : ''}>下一页</button>`;
            
            pagination.innerHTML = html;
        }

        // 跳转页面
        function goToPage(page) {
            if (page < 1 || page > totalPages) return;
            wordPage = page;
            loadWords();
        }

        // 搜索单词
        function searchWords() {
            wordKeyword = document.getElementById('wordSearch').value.trim();
            wordCategory = document.getElementById('wordCategoryFilter').value;
            wordPage = 1;
            loadWords();
        }

        // 回车搜索
        document.getElementById('wordSearch').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchWords();
            }
        });

        // 分类筛选变化
        document.getElementById('wordCategoryFilter').addEventListener('change', function() {
            searchWords();
        });

        // 显示添加单词弹窗
        function showAddWordModal() {
            editingWordId = null;
            document.getElementById('wordModalTitle').textContent = '添加单词';
            document.getElementById('wordCategoryInput').value = '';
            document.getElementById('wordEnglishInput').value = '';
            document.getElementById('wordBritishInput').value = '';
            document.getElementById('wordAmericanInput').value = '';
            document.getElementById('wordDefinitionInput').value = '';
            document.getElementById('wordModal').classList.add('active');
        }

        // 编辑单词
        function editWord(id) {
            editingWordId = id;
            document.getElementById('wordModalTitle').textContent = '编辑单词';
            
            fetch(`/api/admin/word/${id}`)
                .then(res => res.json())
                .then(word => {
                    if (word.error) {
                        showToast(word.error, 'error');
                        return;
                    }
                    
                    document.getElementById('wordCategoryInput').value = word.category_name;
                    document.getElementById('wordEnglishInput').value = word.english_word;
                    document.getElementById('wordBritishInput').value = word.british_phonetic || '';
                    document.getElementById('wordAmericanInput').value = word.american_phonetic || '';
                    document.getElementById('wordDefinitionInput').value = word.chinese_definition;
                    
                    document.getElementById('wordModal').classList.add('active');
                })
                .catch(err => {
                    showToast('加载单词详情失败', 'error');
                });
        }

        // 关闭单词弹窗
        // AI补全单词信息
        function aiCompleteWord() {
            const word = document.getElementById('wordEnglishInput').value.trim();
            const category = document.getElementById('wordCategoryInput').value;
            
            if (!word) {
                showToast('请先输入英文单词', 'error');
                return;
            }
            
            const btn = event.target;
            const originalText = btn.textContent;
            btn.textContent = '生成中...';
            btn.disabled = true;
            
            fetch('/api/ai-complete-word', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    word: word,
                    category: category
                })
            })
            .then(response => response.json())
            .then(data => {
                btn.textContent = originalText;
                btn.disabled = false;
                
                if (data.success) {
                    // 填充音标和释义
                    if (data.british_phonetic) {
                        document.getElementById('wordBritishInput').value = data.british_phonetic;
                    }
                    if (data.american_phonetic) {
                        document.getElementById('wordAmericanInput').value = data.american_phonetic;
                    }
                    if (data.chinese_definition) {
                        document.getElementById('wordDefinitionInput').value = data.chinese_definition;
                    }
                    showToast('AI补全成功', 'success');
                } else {
                    showToast(data.message || 'AI补全失败', 'error');
                }
            })
            .catch(err => {
                console.error('AI补全失败:', err);
                btn.textContent = originalText;
                btn.disabled = false;
                showToast('AI补全失败，请稍后重试', 'error');
            });
        }
        
        function closeWordModal() {
            document.getElementById('wordModal').classList.remove('active');
            editingWordId = null;
        }

        // 保存单词
        function saveWord() {
            const category = document.getElementById('wordCategoryInput').value.trim();
            const english_word = document.getElementById('wordEnglishInput').value.trim();
            const british_phonetic = document.getElementById('wordBritishInput').value.trim();
            const american_phonetic = document.getElementById('wordAmericanInput').value.trim();
            const chinese_definition = document.getElementById('wordDefinitionInput').value.trim();
            
            if (!category || !english_word || !chinese_definition) {
                showToast('请填写必填项', 'error');
                return;
            }
            
            let url, method, data;
            
            if (editingWordId) {
                // 编辑
                url = '/api/admin/word';
                method = 'PUT';
                data = {
                    id: editingWordId,
                    category_name: category,
                    english_word: english_word,
                    british_phonetic: british_phonetic,
                    american_phonetic: american_phonetic,
                    chinese_definition: chinese_definition
                };
            } else {
                // 添加
                url = '/api/admin/word';
                method = 'POST';
                data = {
                    category_name: category,
                    english_word: english_word,
                    british_phonetic: british_phonetic,
                    american_phonetic: american_phonetic,
                    chinese_definition: chinese_definition
                };
            }
            
            fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
            .then(res => res.json())
            .then(result => {
                if (result.error) {
                    showToast(result.error, 'error');
                    return;
                }
                showToast(editingWordId ? '单词已更新' : '单词已添加');
                closeWordModal();
                loadWords();
                loadCategories(); // 更新分类统计
                updateStats();
            })
            .catch(err => {
                showToast('操作失败', 'error');
            });
        }

        // 删除单词
        function deleteWord(id, word) {
            deleteCallback = () => {
                fetch('/api/admin/word', {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: id })
                })
                .then(res => res.json())
                .then(result => {
                    if (result.error) {
                        showToast(result.error, 'error');
                        return;
                    }
                    showToast('单词已删除');
                    loadWords();
                    loadCategories();
                    updateStats();
                })
                .catch(err => {
                    showToast('删除失败', 'error');
                });
            };
            
            document.getElementById('confirmMessage').innerHTML = 
                `确定要删除单词 "<strong>${word}</strong>" 吗？`;
            document.getElementById('confirmWarning').style.display = 'block';
            document.getElementById('confirmWarning').textContent = '⚠️ 此操作不可撤销！';
            document.getElementById('confirmModal').classList.add('active');
        }

        // ==================== 确认弹窗 ====================

        function closeConfirmModal() {
            document.getElementById('confirmModal').classList.remove('active');
            deleteCallback = null;
        }

        function confirmDelete() {
            if (deleteCallback) {
                deleteCallback();
            }
            closeConfirmModal();
        }

        // ==================== 统计更新 ====================

        function updateStats() {
            // 重新加载分类来更新统计
            fetch('/api/admin/categories')
                .then(res => res.json())
                .then(categories => {
                    document.getElementById('categoryCount').textContent = categories.length;
                    const total = categories.reduce((sum, c) => sum + c.count, 0);
                    document.getElementById('totalCount').textContent = total;
                });
        }

        // 点击弹窗外部关闭
        document.querySelectorAll('.modal-overlay').forEach(overlay => {
            overlay.addEventListener('click', function(e) {
                if (e.target === this) {
                    this.classList.remove('active');
                    if (this.id === 'confirmModal') {
                        deleteCallback = null;
                    }
                }
            });
        });

        // 初始化
        loadCategories();
    

        // ==================== 批量修改单词 ====================

        // 全选/取消全选单词
        function toggleSelectAllWords(checkbox) {
            const checkboxes = document.querySelectorAll('.word-checkbox');
            checkboxes.forEach(cb => cb.checked = checkbox.checked);
            updateBatchButton();
        }

        // 更新批量按钮状态
        function updateBatchButton() {
            const checked = document.querySelectorAll('.word-checkbox:checked');
            const updateBtn = document.getElementById('batchUpdateBtn');
            const deleteBtn = document.getElementById('batchDeleteBtn');
            if (updateBtn) {
                updateBtn.style.display = checked.length >= 1 ? 'inline-flex' : 'none';
            }
            if (deleteBtn) {
                deleteBtn.style.display = checked.length >= 1 ? 'inline-flex' : 'none';
            }
        }

        // 显示批量修改分类弹窗
        function showBatchUpdateModal() {
            const checked = document.querySelectorAll('.word-checkbox:checked');
            if (checked.length === 0) {
                showToast('请选择要修改的单词', 'error');
                return;
            }

            // 显示已选择的数量
            document.getElementById('selectedWordsCount').textContent = checked.length;

            // 加载分类选项
            const select = document.getElementById('batchCategoryId');
            select.innerHTML = '<option value="">请选择目标分类</option>';
            
            fetch('/api/admin/categories')
                .then(res => res.json())
                .then(categories => {
                    categories.forEach(cat => {
                        select.innerHTML += `<option value="${cat.id}">${cat.name}</option>`;
                    });
                });

            document.getElementById('batchUpdateWordModal').classList.add('active');
        }

        // 关闭批量修改弹窗
        function closeBatchUpdateModal() {
            document.getElementById('batchUpdateWordModal').classList.remove('active');
        }

        // 确认批量修改分类
        function confirmBatchUpdate() {
            const checked = document.querySelectorAll('.word-checkbox:checked');
            const ids = Array.from(checked).map(cb => parseInt(cb.value));

            const categoryId = document.getElementById('batchCategoryId').value;
            if (!categoryId) {
                showToast('请选择目标分类', 'error');
                return;
            }

            fetch('/api/admin/words/batch', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: ids, data: { category_id: parseInt(categoryId) } })
            })
            .then(res => res.json())
            .then(result => {
                if (result.success) {
                    showToast(result.message);
                    closeBatchUpdateModal();
                    loadWords();
                    updateStats();
                    // 取消全选
                    const selectAll = document.getElementById('selectAllWords');
                    if (selectAll) selectAll.checked = false;
                } else {
                    showToast(result.message || '修改失败', 'error');
                }
            })
            .catch(err => {
                showToast('修改失败', 'error');
            });
        }

        // 显示批量删除弹窗
        function showBatchDeleteModal() {
            const checked = document.querySelectorAll('.word-checkbox:checked');
            if (checked.length === 0) {
                showToast('请选择要删除的单词', 'error');
                return;
            }

            document.getElementById('batchDeleteCount').textContent = checked.length;
            document.getElementById('batchDeleteWordModal').classList.add('active');
        }

        // 关闭批量删除弹窗
        function closeBatchDeleteModal() {
            document.getElementById('batchDeleteWordModal').classList.remove('active');
        }

        // 确认批量删除
        function confirmBatchDelete() {
            const checked = document.querySelectorAll('.word-checkbox:checked');
            const ids = Array.from(checked).map(cb => parseInt(cb.value));

            fetch('/api/admin/words/batch', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: ids })
            })
            .then(res => res.json())
            .then(result => {
                if (result.success) {
                    showToast(result.message);
                    closeBatchDeleteModal();
                    loadWords();
                    updateStats();
                    // 取消全选
                    const selectAll = document.getElementById('selectAllWords');
                    if (selectAll) selectAll.checked = false;
                } else {
                    showToast(result.message || '删除失败', 'error');
                }
            })
            .catch(err => {
                showToast('删除失败', 'error');
            });
        }

        // ==================== 批量导入 ====================
        
        
        // 下载模板
        function downloadTemplate() {
            window.open('/api/admin/template', '_blank');
        }
        
        // 批量导入
        function importWords() {
            const fileInput = document.getElementById('importFile');
            const file = fileInput.files[0];
            
            if (!file) {
                showToast('请选择CSV文件', 'error');
                return;
            }
            
            const formData = new FormData();
            formData.append('file', file);
            
            const importBtn = document.getElementById('importBtn');
            importBtn.disabled = true;
            importBtn.textContent = '导入中...';
            
            const resultDiv = document.getElementById('importResult');
            resultDiv.style.display = 'none';
            resultDiv.className = '';
            
            fetch('/api/admin/import', {
                method: 'POST',
                body: formData
            })
            .then(res => res.json())
            .then(result => {
                if (result.success) {
                    let html = '<div style="color: #28a745; font-weight: bold; margin-bottom: 10px;">✅ 导入完成！</div>';
                    html += '<div style="line-height: 1.8; font-size: 13px;">';
                    html += `<div>新增单词：<strong>${result.added}</strong> 个</div>`;
                    html += `<div>更新单词：<strong>${result.updated}</strong> 个</div>`;
                    html += `<div>跳过：<strong>${result.skipped}</strong> 个</div>`;
                    
                    if (result.errors && result.errors.length > 0) {
                        html += '<div style="margin-top: 10px; color: #d9534f;">错误详情：</div>';
                        html += '<ul style="margin-left: 20px; margin-top: 5px;">';
                        result.errors.forEach(err => {
                            html += `<li>${err}</li>`;
                        });
                        html += '</ul>';
                    }
                    
                    html += '</div>';
                    
                    resultDiv.innerHTML = html;
                    resultDiv.style.display = 'block';
                    resultDiv.style.padding = '20px';
                    resultDiv.style.borderRadius = '8px';
                    resultDiv.style.marginTop = '20px';
                    resultDiv.style.background = '#d4edda';
                    resultDiv.style.border = '1px solid #c3e6cb';
                    resultDiv.style.color = '#155724';
                    
                    showToast('导入成功', 'success');
                    
                    // 重新加载单词列表和分类列表
                    loadWords();
                    loadCategories();
                    updateStats();
                } else {
                    resultDiv.innerHTML = `<div style="color: #d9534f;">❌ ${result.message}</div>`;
                    resultDiv.style.display = 'block';
                    resultDiv.style.padding = '20px';
                    resultDiv.style.borderRadius = '8px';
                    resultDiv.style.marginTop = '20px';
                    resultDiv.style.background = '#f8d7da';
                    resultDiv.style.border = '1px solid #f5c6cb';
                    showToast(result.message || '导入失败', 'error');
                }
            })
            .catch(err => {
                resultDiv.innerHTML = `<div style="color: #d9534f;">❌ 导入失败：${err.message}</div>`;
                resultDiv.style.display = 'block';
                resultDiv.style.padding = '20px';
                resultDiv.style.borderRadius = '8px';
                resultDiv.style.marginTop = '20px';
                resultDiv.style.background = '#f8d7da';
                resultDiv.style.border = '1px solid #f5c6cb';
                showToast('导入失败', 'error');
            })
            .finally(() => {
                importBtn.disabled = false;
                importBtn.textContent = '开始导入';
            });
        }
        
        // 加载导出分类选项
        function loadExportCategories() {
            fetch('/api/admin/categories')
                .then(res => res.json())
                .then(categories => {
                    const select = document.getElementById('exportCategory');
                    select.innerHTML = '<option value="">全部分类</option>';
                    categories.forEach(cat => {
                        select.innerHTML += `<option value="${cat.name}">${cat.name} (${cat.count}个)</option>`;
                    });
                });
        }
        
        // 批量导出
        function exportWords() {
            const category = document.getElementById('exportCategory').value;
            
            let url = '/api/admin/export';
            if (category) {
                url += '?category=' + encodeURIComponent(category);
            }
            
            // 直接下载
            window.location.href = url;
            
            showToast('导出成功', 'success');
        }

        // ==================== 日志管理 ====================
        
        // 日志分页
        let logPage = 1;
        let logPageSize = 20;
        let logAction = '';
        let logArchived = '0';  // 0: 未归档, 1: 已归档
        let totalLogs = 0;
        let totalLogPages = 0;
        let autoArchiveChecked = false;  // 是否已检查过自动归档
        
        // 加载日志列表
        // 加载所有操作类型
        function loadLogActions() {
            fetch('/api/admin/log-actions')
            .then(res => res.json())
            .then(data => {
                const select = document.getElementById('logActionFilter');
                const currentValue = select.value;
                
                // 保留"全部操作"选项，清空其他选项
                select.innerHTML = '<option value="">全部操作</option>';
                
                // 添加从数据库获取的操作类型
                if (data.actions && data.actions.length > 0) {
                    data.actions.forEach(action => {
                        const option = document.createElement('option');
                        option.value = action;
                        option.textContent = action;
                        select.appendChild(option);
                    });
                }
                
                // 恢复之前选中的值
                select.value = currentValue;
            })
            .catch(err => {
                console.error('加载操作类型失败:', err);
            });
        }

        function loadLogs() {
            const tbody = document.getElementById('logTableBody');
            tbody.innerHTML = '<tr><td colspan="6" class="loading">加载中...</td></tr>';
            
            let url = `/api/admin/logs?page=${logPage}&per_page=${logPageSize}`;
            if (logAction) url += `&action=${encodeURIComponent(logAction)}`;
            url += `&archived=${logArchived}`;
            
            fetch(url)
                .then(res => res.json())
                .then(result => {
                    const logs = result.logs;
                    totalLogs = result.total;
                    totalLogPages = result.total_pages;
                    
                    // 更新按钮显示
                    updateLogButtons();
                    
                    if (logs.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="6" class="empty">暂无日志</td></tr>';
                    } else {
                        let html = '';
                        logs.forEach(log => {
                            html += `
                            <tr>
                                <td><input type="checkbox" class="log-checkbox" value="${log.id}" onchange="updateLogButtons()"></td>
                                <td>${log.created_at}</td>
                                <td><span class="category-tag">${log.action}</span></td>
                                <td style="max-width: 400px;">${log.description || '-'}</td>
                                <td>${log.ip_address || '-'}</td>
                                <td>
                                    <div class="action-buttons">
                                        ${logArchived === '0' 
                                            ? `<button class="btn btn-sm" style="background: #5bc0de; color: white; border-color: #5bc0de;" onclick="archiveLog(${log.id})">归档</button>`
                                            : `<button class="btn btn-sm" style="background: #f0ad4e; color: white; border-color: #f0ad4e;" onclick="unarchiveLog(${log.id})">取消归档</button>`
                                        }
                                        <button class="btn btn-sm btn-danger" onclick="deleteLog(${log.id})">删除</button>
                                    </div>
                                </td>
                            </tr>
                            `;
                        });
                        tbody.innerHTML = html;
                    }
                    
                    // 更新分页
                    renderLogPagination();
                    
                    // 自动归档超过90天的日志（只检查一次）
                    if (!autoArchiveChecked && logArchived === '0') {
                        autoArchiveChecked = true;
                        autoArchiveLogs();
                    }
                })
                .catch(err => {
                    tbody.innerHTML = '<tr><td colspan="6" class="empty">加载失败</td></tr>';
                    showToast('加载日志失败', 'error');
                });
        }

        // 自动归档超过90天的日志
        function autoArchiveLogs() {
            fetch('/api/admin/logs/auto-archive', {
                method: 'POST'
            })
            .then(res => res.json())
            .then(result => {
                if (result.success && result.archived_count > 0) {
                    showToast(result.message);
                    loadLogs();  // 重新加载日志列表
                }
            })
            .catch(err => {
                // 自动归档失败不提示，不影响用户体验
            });
        }

        // 更新日志按钮显示
        function updateLogButtons() {
            const checked = document.querySelectorAll('.log-checkbox:checked');
            const archiveBtn = document.getElementById('archiveBtn');
            const unarchiveBtn = document.getElementById('unarchiveBtn');
            const clearBtn = document.getElementById('clearLogsBtn');
            
            if (logArchived === '0') {
                // 正常日志：显示归档按钮，隐藏取消归档按钮
                if (archiveBtn) archiveBtn.style.display = checked.length >= 1 ? 'inline-flex' : 'none';
                if (unarchiveBtn) unarchiveBtn.style.display = 'none';
                if (clearBtn) clearBtn.innerHTML = '<span>🗑️</span> 清空日志';
            } else {
                // 归档日志：显示取消归档按钮，隐藏归档按钮
                if (archiveBtn) archiveBtn.style.display = 'none';
                if (unarchiveBtn) unarchiveBtn.style.display = checked.length >= 1 ? 'inline-flex' : 'none';
                if (clearBtn) clearBtn.innerHTML = '<span>🗑️</span> 清空归档';
            }
        }

        // 切换日志标签
        function switchLogTab(archived) {
            logArchived = archived;
            logPage = 1;
            
            // 更新标签样式
            document.querySelectorAll('.log-tab').forEach(tab => {
                if (tab.dataset.archived === archived) {
                    tab.classList.add('active');
                    tab.style.background = '#2E75B6';
                    tab.style.color = 'white';
                } else {
                    tab.classList.remove('active');
                    tab.style.background = '#f5f7fa';
                    tab.style.color = '#666';
                }
            });
            
            // 取消全选
            const selectAll = document.getElementById('selectAllLogs');
            if (selectAll) selectAll.checked = false;
            
            loadLogs();
        }

        // 全选/取消全选日志
        function toggleSelectAllLogs(checkbox) {
            const checkboxes = document.querySelectorAll('.log-checkbox');
            checkboxes.forEach(cb => cb.checked = checkbox.checked);
            updateLogButtons();
        }

        // 归档单条日志
        function archiveLog(id) {
            fetch('/api/admin/log/archive', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: [id] })
            })
            .then(res => res.json())
            .then(result => {
                if (result.success) {
                    showToast(result.message);
                    loadLogs();
                } else {
                    showToast(result.message || '归档失败', 'error');
                }
            })
            .catch(err => {
                showToast('归档失败', 'error');
            });
        }

        // 批量归档日志
        function archiveLogs() {
            const checked = document.querySelectorAll('.log-checkbox:checked');
            if (checked.length === 0) {
                showToast('请选择要归档的日志', 'error');
                return;
            }
            
            const ids = Array.from(checked).map(cb => parseInt(cb.value));
            
            fetch('/api/admin/log/archive', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: ids })
            })
            .then(res => res.json())
            .then(result => {
                if (result.success) {
                    showToast(result.message);
                    loadLogs();
                    // 取消全选
                    const selectAll = document.getElementById('selectAllLogs');
                    if (selectAll) selectAll.checked = false;
                } else {
                    showToast(result.message || '归档失败', 'error');
                }
            })
            .catch(err => {
                showToast('归档失败', 'error');
            });
        }

        // 取消归档单条日志
        function unarchiveLog(id) {
            fetch('/api/admin/log/unarchive', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: [id] })
            })
            .then(res => res.json())
            .then(result => {
                if (result.success) {
                    showToast(result.message);
                    loadLogs();
                } else {
                    showToast(result.message || '取消归档失败', 'error');
                }
            })
            .catch(err => {
                showToast('取消归档失败', 'error');
            });
        }

        // 批量取消归档日志
        function unarchiveLogs() {
            const checked = document.querySelectorAll('.log-checkbox:checked');
            if (checked.length === 0) {
                showToast('请选择要取消归档的日志', 'error');
                return;
            }
            
            const ids = Array.from(checked).map(cb => parseInt(cb.value));
            
            fetch('/api/admin/log/unarchive', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: ids })
            })
            .then(res => res.json())
            .then(result => {
                if (result.success) {
                    showToast(result.message);
                    loadLogs();
                    // 取消全选
                    const selectAll = document.getElementById('selectAllLogs');
                    if (selectAll) selectAll.checked = false;
                } else {
                    showToast(result.message || '取消归档失败', 'error');
                }
            })
            .catch(err => {
                showToast('取消归档失败', 'error');
            });
        }
        
        // 渲染日志分页
        function renderLogPagination() {
            const pagination = document.getElementById('logPagination');
            
            if (totalLogPages <= 1) {
                pagination.innerHTML = '';
                return;
            }
            
            let html = '';
            html += `<button onclick="goToLogPage(${logPage - 1})" ${logPage === 1 ? 'disabled' : ''}>上一页</button>`;
            html += `<span class="page-info">第 ${logPage} / ${totalLogPages} 页，共 ${totalLogs} 条</span>`;
            html += `<button onclick="goToLogPage(${logPage + 1})" ${logPage === totalLogPages ? 'disabled' : ''}>下一页</button>`;
            
            pagination.innerHTML = html;
        }
        
        // 跳转日志页面
        function goToLogPage(page) {
            if (page < 1 || page > totalLogPages) return;
            logPage = page;
            loadLogs();
        }
        
        // 搜索日志（按操作类型筛选）
        function searchLogs() {
            logAction = document.getElementById('logActionFilter').value;
            logPage = 1;
            loadLogs();
        }
        
        // 删除单条日志
        function deleteLog(id) {
            deleteCallback = () => {
                fetch(`/api/admin/log/${id}`, {
                    method: 'DELETE'
                })
                .then(res => res.json())
                .then(result => {
                    if (result.error) {
                        showToast(result.error, 'error');
                        return;
                    }
                    showToast('日志已删除');
                    loadLogs();
                })
                .catch(err => {
                    showToast('删除失败', 'error');
                });
            };
            
            document.getElementById('confirmMessage').innerHTML = 
                '确定要删除这条日志吗？';
            document.getElementById('confirmWarning').style.display = 'block';
            document.getElementById('confirmWarning').textContent = '⚠️ 此操作不可撤销！';
            document.getElementById('confirmModal').classList.add('active');
        }
        
        // 清空日志
        function clearLogs() {
            deleteCallback = () => {
                let url = '/api/admin/logs';
                let successMsg = '已清空日志';
                
                if (logArchived === '1') {
                    url = '/api/admin/logs/archived';
                    successMsg = '已永久删除归档日志';
                }
                
                fetch(url, {
                    method: 'DELETE'
                })
                .then(res => res.json())
                .then(result => {
                    if (result.error) {
                        showToast(result.error, 'error');
                        return;
                    }
                    showToast(successMsg);
                    loadLogs();
                })
                .catch(err => {
                    showToast('清空失败', 'error');
                });
            };
            
            if (logArchived === '1') {
                document.getElementById('confirmMessage').innerHTML = 
                    '确定要永久删除所有归档日志吗？';
                document.getElementById('confirmWarning').style.display = 'block';
                document.getElementById('confirmWarning').textContent = '⚠️ 此操作将永久删除所有归档日志，不可撤销！';
            } else {
                document.getElementById('confirmMessage').innerHTML = 
                    '确定要清空所有日志吗？';
                document.getElementById('confirmWarning').style.display = 'block';
                document.getElementById('confirmWarning').textContent = '⚠️ 此操作将删除所有日志记录，不可撤销！';
            }
            document.getElementById('confirmModal').classList.add('active');
        }

        // ==================== 密码修改 ====================
        
        function changePassword() {
            const oldPassword = document.getElementById('oldPassword').value;
            const newPassword = document.getElementById('newPassword').value;
            const confirmPassword = document.getElementById('confirmPassword').value;
            
            if (!oldPassword) {
                showToast('请输入旧密码', 'error');
                return;
            }
            
            if (!newPassword) {
                showToast('请输入新密码', 'error');
                return;
            }
            
            if (newPassword.length < 4) {
                showToast('新密码至少4位', 'error');
                return;
            }
            
            if (newPassword !== confirmPassword) {
                showToast('两次输入的新密码不一致', 'error');
                return;
            }
            
            fetch('/api/admin/change-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    old_password: oldPassword,
                    new_password: newPassword,
                    confirm_password: confirmPassword
                })
            })
            .then(res => res.json())
            .then(result => {
                if (!result.success) {
                    showToast(result.message || '修改失败', 'error');
                    return;
                }
                
                showToast('密码修改成功，即将跳转到登录页');
                
                // 清空输入框
                document.getElementById('oldPassword').value = '';
                document.getElementById('newPassword').value = '';
                document.getElementById('confirmPassword').value = '';
                
                // 2秒后跳转到登录页
                setTimeout(() => {
                    window.location.href = '/login';
                }, 2000);
            })
            .catch(err => {
                showToast('修改失败', 'error');
            });
        }

        // 切换设置标签
        function switchSettingTab(tab) {
            // 移除所有标签的active状态（内容区域的标签，现在可能已经移除了，但保留兼容）
            const tabs = document.querySelectorAll('.settings-tab');
            if (tabs.length > 0) {
                tabs.forEach(t => {
                    t.classList.remove('active');
                });
                document.getElementById('tab-' + tab).classList.add('active');
            }
            
            // 更新顶部子导航的选中状态
            document.querySelectorAll('.subnav-item').forEach(item => {
                item.classList.remove('active');
            });
            document.getElementById('subnav-' + tab).classList.add('active');
            
            // 隐藏所有面板
            document.querySelectorAll('.settings-panel').forEach(p => {
                p.classList.remove('active');
            });
            
            // 激活选中的面板
            document.getElementById('panel-' + tab).classList.add('active');
            
            // 如果切换到站点信息，加载设置
            if (tab === 'site') {
                loadSiteSettings();
            }
            
            // 如果切换到AI设置，加载AI配置
            if (tab === 'ai') {
                loadAISettings();
            }
        }

        // 切换批量导入导出标签
        function switchImportTab(tab) {
            // 更新顶部子导航的选中状态
            document.querySelectorAll('#importSubnav .subnav-item').forEach(item => {
                item.classList.remove('active');
            });
            document.getElementById('subnav-' + tab).classList.add('active');
            
            // 隐藏所有面板
            document.querySelectorAll('.import-panel').forEach(p => {
                p.classList.remove('active');
            });
            
            // 激活选中的面板
            document.getElementById('panel-' + tab).classList.add('active');
            
            // 如果切换到导出，加载分类选项
            if (tab === 'export') {
                loadExportCategories();
            }
        }

        // 加载站点设置
        function loadSiteSettings() {
            fetch('/api/admin/settings')
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    showToast(data.error, 'error');
                    return;
                }
                
                document.getElementById('siteName').value = data.site_name || '';
                document.getElementById('siteDescription').value = data.site_description || '';
                document.getElementById('siteKeywords').value = data.site_keywords || '';
                document.getElementById('siteCopyright').value = data.site_copyright || '';
                document.getElementById('siteIcp').value = data.site_icp || '';
            })
            .catch(err => {
                showToast('加载站点设置失败', 'error');
            });
        }

        // 保存站点设置
        function saveSiteSettings() {
            const siteName = document.getElementById('siteName').value.trim();
            const siteDescription = document.getElementById('siteDescription').value.trim();
            const siteKeywords = document.getElementById('siteKeywords').value.trim();
            const siteCopyright = document.getElementById('siteCopyright').value.trim();
            const siteIcp = document.getElementById('siteIcp').value.trim();
            
            if (!siteName) {
                showToast('站点名称不能为空', 'error');
                return;
            }
            
            fetch('/api/admin/settings', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    site_name: siteName,
                    site_description: siteDescription,
                    site_keywords: siteKeywords,
                    site_copyright: siteCopyright,
                    site_icp: siteIcp
                })
            })
            .then(res => res.json())
            .then(result => {
                if (!result.success) {
                    showToast(result.message || '保存失败', 'error');
                    return;
                }
                
                showToast('站点设置保存成功');
            })
            .catch(err => {
                showToast('保存失败', 'error');
            });
        }



        // ==================== AI助手相关功能 ====================

        // 加载聊天历史
        function loadAIChatHistory() {
            fetch('/api/admin/ai-chat-history')
            .then(res => res.json())
            .then(result => {
                if (!result.success) {
                    return;
                }
                
                const chatMessages = document.getElementById('chatMessages');
                if (!chatMessages) return;
                
                // 清空原有消息（保留欢迎消息）
                const welcomeMsg = chatMessages.querySelector('.ai-message');
                chatMessages.innerHTML = '';
                if (welcomeMsg && result.history.length === 0) {
                    chatMessages.appendChild(welcomeMsg);
                    return;
                }
                
                // 添加历史消息
                result.history.forEach(msg => {
                    addChatMessage(msg.role, msg.content);
                });
                
                // 滚动到底部
                chatMessages.scrollTop = chatMessages.scrollHeight;
            })
            .catch(err => {
                console.error('加载聊天历史失败:', err);
            });
        }

        // 添加聊天消息
        function addChatMessage(role, content) {
            const chatMessages = document.getElementById('chatMessages');
            if (!chatMessages) return;
            
            const messageDiv = document.createElement('div');
            messageDiv.className = 'chat-message ' + (role === 'user' ? 'user-message' : 'ai-message');
            
            const avatar = document.createElement('div');
            avatar.className = 'message-avatar';
            avatar.textContent = role === 'user' ? '👤' : '🤖';
            
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            
            // 处理内容，支持换行
            const lines = content.split('\n');
            lines.forEach(line => {
                if (line.trim()) {
                    const p = document.createElement('p');
                    p.textContent = line;
                    contentDiv.appendChild(p);
                }
            });
            
            messageDiv.appendChild(avatar);
            messageDiv.appendChild(contentDiv);
            
            chatMessages.appendChild(messageDiv);
            
            // 滚动到底部
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        // 显示打字指示器
        function showTypingIndicator() {
            const chatMessages = document.getElementById('chatMessages');
            if (!chatMessages) return;
            
            const messageDiv = document.createElement('div');
            messageDiv.className = 'chat-message ai-message';
            messageDiv.id = 'typingIndicator';
            
            const avatar = document.createElement('div');
            avatar.className = 'message-avatar';
            avatar.textContent = '🤖';
            
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            
            const typingDiv = document.createElement('div');
            typingDiv.className = 'typing-indicator';
            typingDiv.innerHTML = '<span></span><span></span><span></span>';
            
            contentDiv.appendChild(typingDiv);
            messageDiv.appendChild(avatar);
            messageDiv.appendChild(contentDiv);
            
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        // 隐藏打字指示器
        function hideTypingIndicator() {
            const indicator = document.getElementById('typingIndicator');
            if (indicator) {
                indicator.remove();
            }
        }

        // 发送AI消息
        function sendAIMessage() {
            const input = document.getElementById('chatInput');
            if (!input) return;
            
            const message = input.value.trim();
            if (!message) {
                showToast('请输入消息', 'error');
                return;
            }
            
            // 添加用户消息
            addChatMessage('user', message);
            
            // 清空输入框
            input.value = '';
            
            // 显示打字指示器
            showTypingIndicator();
            
            // 发送请求
            fetch('/api/admin/ai-chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: message })
            })
            .then(res => res.json())
            .then(result => {
                // 隐藏打字指示器
                hideTypingIndicator();
                
                if (!result.success) {
                    addChatMessage('assistant', '❌ ' + (result.message || '发送失败'));
                    return;
                }
                
                // 添加AI回复
                addChatMessage('assistant', result.reply);
                
                // 如果有操作结果，刷新相关数据
                if (result.action_result && result.action_result.success) {
                    // 操作成功，刷新分类和单词数据
                    loadCategories();
                    updateStats();
                }
            })
            .catch(err => {
                hideTypingIndicator();
                addChatMessage('assistant', '❌ 请求失败：' + err.message);
            });
        }

        // 清空聊天历史
        function clearAIChat() {
            if (!confirm('确定要清空所有聊天记录吗？')) {
                return;
            }
            
            fetch('/api/admin/ai-chat-history', {
                method: 'DELETE'
            })
            .then(res => res.json())
            .then(result => {
                if (!result.success) {
                    showToast(result.message || '清空失败', 'error');
                    return;
                }
                
                showToast('聊天记录已清空');
                
                // 重新加载（会显示欢迎消息）
                const chatMessages = document.getElementById('chatMessages');
                if (chatMessages) {
                    chatMessages.innerHTML = '';
                    loadAIChatHistory();
                }
            })
            .catch(err => {
                showToast('清空失败', 'error');
            });
        }

        // 加载AI设置
        function loadAISettings() {
            fetch('/api/admin/ai-settings')
            .then(res => res.json())
            .then(result => {
                if (!result.success || !result.data) {
                    return;
                }
                
                const data = result.data;
                document.getElementById('aiApiKey').value = data.api_key || '';
                document.getElementById('aiApiUrl').value = data.api_url || '';
                document.getElementById('aiModelName').value = data.model_name || '';
                document.getElementById('aiSystemPrompt').value = data.system_prompt || '';
            })
            .catch(err => {
                showToast('加载AI设置失败', 'error');
            });
        }

        // 保存AI设置
        function saveAISettings() {
            const apiKey = document.getElementById('aiApiKey').value.trim();
            const apiUrl = document.getElementById('aiApiUrl').value.trim();
            const modelName = document.getElementById('aiModelName').value.trim();
            const systemPrompt = document.getElementById('aiSystemPrompt').value.trim();
            
            if (!apiUrl) {
                showToast('API地址不能为空', 'error');
                return;
            }
            
            fetch('/api/admin/ai-settings', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    api_key: apiKey,
                    api_url: apiUrl,
                    model_name: modelName,
                    system_prompt: systemPrompt
                })
            })
            .then(res => res.json())
            .then(result => {
                if (!result.success) {
                    showToast(result.message || '保存失败', 'error');
                    return;
                }
                
                showToast('AI设置保存成功');
            })
            .catch(err => {
                showToast('保存失败', 'error');
            });
        }

        // 聊天输入框的Enter键发送
        document.addEventListener('DOMContentLoaded', function() {
            const chatInput = document.getElementById('chatInput');
            if (chatInput) {
                chatInput.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        sendAIMessage();
                    }
                });
            }
        });
