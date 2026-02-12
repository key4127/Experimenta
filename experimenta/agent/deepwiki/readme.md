simple_chat.chat_completions_stream
→ RAG.prepare_retriever → DatabaseManager.prepare_database → _create_repo / prepare_db_index → read_all_documents、transform_documents_and_save_to_db
→ RAG.call → self.retriever(query)（FAISSRetriever）
→ 同文件内拼 context_text、prompt，再在 response_stream() 里
→ model.acall(...) 或 model.generate_content(...)，循环 yield 文本