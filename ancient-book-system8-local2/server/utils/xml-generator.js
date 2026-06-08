module.exports = function generateXML(document, annotations, characters) {
    let xml = `<?xml version="1.0" encoding="UTF-8"?>\n`;
    xml += `<AncientBookProject>\n`;

    // 1. 文档元数据
    xml += `  <MetaInfo>\n`;
    xml += `    <DocID>${document.id}</DocID>\n`;
    xml += `    <FileName><![CDATA[${document.title || '未命名'}]]></FileName>\n`;
    xml += `    <ExportTime>${new Date().toLocaleString()}</ExportTime>\n`;
    xml += `  </MetaInfo>\n`;

    // 2. 详细批注记录 (包含原文和 AI 讲解)
    xml += `  <AnnotationRecords count="${annotations.length}">\n`;
    annotations.forEach(ann => {
        xml += `    <Item id="${ann.id}">\n`;
        xml += `      <Page>${ann.page_number || 1}</Page>\n`;
        xml += `      <Original><![CDATA[${ann.original_text || ''}]]></Original>\n`;
        xml += `      <Simplified><![CDATA[${ann.simplified_text || ''}]]></Simplified>\n`;
        xml += `      <AI_Master_Explanation><![CDATA[${ann.ai_analysis || ''}]]></AI_Master_Explanation>\n`;
        xml += `      <User_Definition>\n`;
        xml += `        <Type>${ann.mark_type || '字'}</Type>\n`;
        xml += `        <Meaning><![CDATA[${ann.meaning || ''}]]></Meaning>\n`;
        xml += `        <Notes><![CDATA[${ann.notes || ''}]]></Notes>\n`;
        xml += `      </User_Definition>\n`;
        xml += `      <AuditStatus>${ann.status || '待审'}</AuditStatus>\n`;
        xml += `    </Item>\n`;
    });
    xml += `  </AnnotationRecords>\n`;

    // 3. 仓颉造字字库
    xml += `  <CharacterLibrary count="${characters.length}">\n`;
    characters.forEach(char => {
        xml += `    <CharItem>\n`;
        xml += `      <Unicode>${char.unicode_code || ''}</Unicode>\n`;
        xml += `      <Pinyin><![CDATA[${char.character_name || ''}]]></Pinyin>\n`;
        xml += `      <Etymology><![CDATA[${char.description || ''}]]></Etymology>\n`;
        // Image 数据单独存放
        xml += `      <Image>\n        <![CDATA[${char.character_image || ''}]]>\n      </Image>\n`;
        xml += `    </CharItem>\n`;
    });
    xml += `  </CharacterLibrary>\n`;

    xml += `</AncientBookProject>`;
    return xml;
};